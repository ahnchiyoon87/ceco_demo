"""Real loopback Modbus TCP, ephemeral port, independent plant, no MQTT."""
from pathlib import Path
import struct
import unittest

import yaml
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.server import ModbusTcpServer
from sim import Simulator


class CoolingTCPTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        cfg = yaml.safe_load(Path(__file__).with_name("plant.yaml").read_text(encoding="utf-8"))
        cfg["autopilot"]["enabled"] = False
        cfg["noise"] = {tag: 0 for tag in cfg["noise"]}
        self.sim = Simulator(cfg)
        self.sim.plant.temp_c = self.sim.plant.jacket_c = 100
        self.server = ModbusTcpServer(self.sim.context, address=("127.0.0.1", 0))
        await self.server.serve_forever(background=True)
        port = self.server.transport.sockets[0].getsockname()[1]
        self.client = AsyncModbusTcpClient("127.0.0.1", port=port, retries=0)
        self.assertTrue(await self.client.connect())

    async def asyncTearDown(self):
        self.client.close()
        await self.server.shutdown()

    async def test_command_ack_readback_and_actual_temperature_are_distinct(self):
        ack = await self.client.write_coil(3, True, slave=1)
        self.assertFalse(ack.isError())
        # A Modbus acknowledgement precedes the plant scan and is not recovery.
        self.assertFalse(self.sim.snapshot()["commands"]["cooler_enable"])
        self.sim.scan()
        before = self.sim.snapshot()
        coil = await self.client.read_coils(3, count=1, slave=1)
        self.assertTrue(coil.bits[0])
        self.assertTrue(before["commands"]["cooler_enable"])
        for _ in range(120):
            self.sim.scan()
        after = self.sim.snapshot()
        registers = await self.client.read_holding_registers(4, count=2, slave=1)
        wire_temperature = struct.unpack(">f", struct.pack(">HH", *registers.registers))[0]
        self.assertGreater(after["seq"], before["seq"])
        self.assertLess(wire_temperature, before["readings"]["TT-101"] - 3)
        self.assertAlmostEqual(wire_temperature, after["readings"]["TT-101"], places=3)

    async def test_successful_write_with_failed_cooling_does_not_remove_fault(self):
        self.sim.plant.inject("cooling_loss", 600)
        ack = await self.client.write_coil(3, True, slave=1)
        self.assertFalse(ack.isError())
        self.sim.scan()
        state = self.sim.snapshot()
        self.assertTrue(state["commands"]["cooler_enable"])
        self.assertEqual(state["thermal_model"]["cooler_kw"], 0)
        self.assertIn("cooling_loss", state["active_faults"])


if __name__ == "__main__":
    unittest.main()
