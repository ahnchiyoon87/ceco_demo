-- L4-12 시도: 내장 Python UDF 에서 onnxruntime 을 불러 본다.
-- 문서: 내장 Python UDF 는 json·decimal·re·math·datetime 만 허용 — 엔진의 실제 거부 메시지를 기록하는 것이 목적.
CREATE FUNCTION onnx_probe(x DOUBLE PRECISION) RETURNS DOUBLE PRECISION LANGUAGE python AS $$
import onnxruntime
def onnx_probe(x):
    return x
$$;
SELECT onnx_probe(1.0);
