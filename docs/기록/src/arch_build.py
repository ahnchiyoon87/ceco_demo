# -*- coding: utf-8 -*-
"""ceco_demo 마스터 가이드 2부(시스템 아키텍처 상세) 본문 생성기(hyd-iot-edu docs/src/arch_build.py 와 같은 방식).
2026-10-07 사용자 "마스터가이드하나만 존재하면됨" → 별도 문서를 만들지 않고 master_build.py 가 build_html(sec_offset, out=None) 으로 본문을 받아 넣는다.
아래 build_pdf / __main__ 의 별도 파일 생성은 쓰지 않는다(직접 실행하면 마스터 가이드를 다시 만든다).
데이터는 arch_data.py, 그림은 arch_fig.py, 본문 틀은 arch_tpl.html.
  python arch_build.py          → HTML + PDF
  python arch_build.py --html   → HTML 만
부품 번호 ①~㊲은 마스터_가이드(master_arch_svg.py)와 같은지 빌드마다 대조한다.
"""
import collections, html, pathlib, re, sys

HERE = pathlib.Path(__file__).resolve().parent
DOCS = HERE.parent.parent
OUT_HTML = DOCS / "시스템_아키텍처.html"
OUT_PDF = DOCS / "시스템_아키텍처.pdf"
sys.path.insert(0, str(HERE))
from arch_data import PART, NO, L, D, C, CIRC, ZONE_NAME, MASTER_ALIAS  # noqa: E402
import arch_fig  # noqa: E402

COL = dict(data="#1f6f8b", cmd="#d1343f", alert="#7b4fc9", api="#4a5fb5", mon="#7d8890", once="#8f989f", human="#2b2f33")
KINDW = {"data": "계측 · 기록", "cmd": "요청 · 명령 · 실행", "alert": "경보", "api": "조회 · 호출", "mon": "감시", "once": "기동 때 1회", "human": "사람"}
DIRW = {"fwd": "여는 쪽 → 받는 쪽", "back": "받는 쪽 → 여는 쪽", "both": "양쪽"}


def n(k):
    return f'<a class="nref nz-{PART[k][3]}" href="#p{NO[k]}" title="{html.escape(PART[k][1])}">{CIRC[NO[k]]}</a>'


def nn(k):
    return f'{n(k)}&nbsp;{PART[k][1]}'


def c(k):
    x = L[k]
    return f'<a class="cref k-{x["kind"]}" href="#c{x["no"]}">C{x["no"]}</a>'


def sub(t):
    t = re.sub(r"\{nn:(\w+)\}", lambda m: nn(m.group(1)), t)
    t = re.sub(r"\{n:(\w+)\}", lambda m: n(m.group(1)), t)
    return re.sub(r"\{c:(\w+)\}", lambda m: c(m.group(1)), t)


def part_cards():
    out = []
    for k, (no, title, prod, zone, kind) in PART.items():
        easy, spec, more = D[k]
        rel = [x for x in L.values() if x["a"] == k or x["b"] == k or (isinstance(x["b"], list) and k in x["b"])]
        if k == "router":
            rel = [L[x] for x in ("bridge_out", "bridge_in", "otag_rw", "coll_sub", "coll_disp", "coll_gw", "graf_dmzi", "ai_dmzi", "prom_fed", "host_router")]
        chip = {"once": "기동 때 1회", "mon": "감시 프로필(make up-full)", "ext": "밖"}.get(kind, "")
        spec_html = "".join(f"<dt>{a}</dt><dd>{b}</dd>" for a, b in spec)
        out.append(
            f'<article class="part pz-{zone}" id="p{no}">'
            f'<header><span class="pnum">{CIRC[no]}</span><h3>{title}</h3><span class="zchip">{ZONE_NAME[zone]}</span>'
            + (f'<span class="kchip">{chip}</span>' if chip else "") + "</header>"
            f'<div class="easy"><span class="lane">쉬운 말</span><p>{sub(easy)}</p></div>'
            f'<div class="tech"><span class="lane">기술 세부</span><dl class="spec">{sub(spec_html)}</dl>{sub(more)}</div>'
            f'<p class="rel">닿는 연결{"(라우터를 지나는 것)" if k == "router" else ""}: {" ".join(c(x["key"]) for x in rel) if rel else "없음"}</p></article>')
    return "\n".join(out)


def line_rows(routed):
    out = []
    for k, x in L.items():
        bs = x["b"] if isinstance(x["b"], list) else [x["b"]]
        proto, what = C[k]
        shown = "" if k in routed else '<span class="nodraw">그림: 상자 위 작은 표</span>'
        out.append(f'<li class="cline lk-{x["kind"]}" id="c{x["no"]}"><span class="cnum k-{x["kind"]}">C{x["no"]}</span><div>'
                   f'<p class="ends">● {nn(x["a"])} <span class="arrow">→</span> {", ".join(nn(b) for b in bs)}</p>'
                   f'<p class="meta"><span>{KINDW[x["kind"]]}</span><span>데이터: {DIRW[x["dir"]]}</span>{shown}</p>'
                   f'<p class="proto">{sub(proto)}</p><p>{sub(what)}</p></div></li>')
    return "\n".join(out)


def check_master_numbers():
    src = (HERE / "master_arch_svg.py").read_text(encoding="utf-8")
    mp = {MASTER_ALIAS.get(k, k): int(v) for k, v in re.findall(r'box\("(\w+)", (\d+),', src) if int(v) > 0}
    bad = [(k, v, NO.get(k)) for k, v in mp.items() if NO.get(k) != v]
    assert not bad, f"마스터 가이드와 번호 불일치: {bad}"
    return len(mp)


def build_html(sec_offset=0, out=None):
    nmaster = check_master_numbers()
    fig, routed, over1, (fw, fh) = arch_fig.svg(PART, L, COL, CIRC, compact=False, idp="a")
    figo, _r, over2, _s = arch_fig.svg(PART, L, COL, CIRC, compact=True, idp="o")
    over = over1 + over2
    assert not over, "그림 글자 넘침: " + "; ".join(f"{k}: {t}" for k, t in over)
    pw = 600
    s = (HERE / "arch_tpl.html").read_text(encoding="utf-8")
    # 기술 레이어 구조도 · 시퀀스 · 리니지 · 속 구조 · 부록
    import arch_layers as AL, arch_layers_ceco as LC, arch_layers_ceco_text as LT, arch_extra as AX, arch_internal as AI, arch_lineage as ALN, arch_appendix_ceco as APX
    lsvg, (lw, lh) = AL.svg(LC.LAYERS, LC.CARDS, LC.ARROWS, LC.NCOL)
    said = {int(x) for e, _t in LT.LAYER_TEXT.values() for x in re.findall(r"\{a:(\d+)\}", e)}
    allno = set(range(1, len(LC.ARROWS) + 1))
    assert said == allno, f"층별 글에 없는 화살표: {sorted(allno - said)} · 없는 번호: {sorted(said - allno)}"
    assert set(LT.LAYER_TEXT) == {x[0] for x in LC.LAYERS}
    ssvg, (sw, sh) = AL.seq_svg(LT.SEQ_LANES, LT.SEQ_PHASES, LT.SEQ)
    assert len(LT.SEQ_STORY) == len(LT.SEQ_PHASES)
    lpw, spw = 560, 440
    lfig, sfig = round((lpw - 16) * lh / lw), round((spw - 16) * sh / sw)
    assert set(LT.LINEAGE_EASY) == set(ALN.LINEAGE), set(LT.LINEAGE_EASY) ^ set(ALN.LINEAGE)
    assert set(LT.INTERNAL_EASY) == set(AI.INTERNAL), set(LT.INTERNAL_EASY) ^ set(AI.INTERNAL)
    nhop = sum(len(d["hops"]) for d in ALN.LINEAGE.values())
    apx, names = APX.build()
    figtxt = " ".join(" ".join([c["title"], c.get("tech", ""), c.get("box", "")] + c.get("lines", [])) for c in LC.CARDS.values()) + " " + " ".join(a[3] + " " + a[4] for a in LC.ARROWS)
    miss = {k: [x for x in names[k] if x not in figtxt] for k in ("services", "volumes", "networks", "kafka")}
    assert not any(miss.values()), f"기술 레이어 구조도에 없는 요소: { {k: v for k, v in miss.items() if v} }"
    ex = dict(**{"<!--LEGEND_L-->": AL.legend_html(), "<!--SVG_LAYERS-->": lsvg, "<!--LAYER_TEXT-->": AL.layer_text_html(LC.LAYERS, LC.CARDS, LC.ARROWS, LT.LAYER_TEXT),
              "<!--ARROW_TABLE-->": AL.table(LC.ARROWS, LC.CARDS, LC.LAYERS), "<!--LAYER_TABLE-->": AL.layer_table_html(LT.LAYER_TABLE),
              "<!--SVG_SEQ-->": ssvg, "<!--SEQ_NOTE-->": html.escape(LT.SEQ_NOTE), "<!--SEQ_STORY-->": AL.seq_story_html(LT.SEQ_PHASES, LT.SEQ, LT.SEQ_STORY),
              "<!--LINEAGE-->": AX.lineage_html(ALN.LINEAGE, easy=LT.LINEAGE_EASY),
              "<!--CAUTION-->": '<ol class="caution">' + "".join(f"<li>{html.escape(x)}</li>" for x in ALN.CAUTION) + "</ol>",
              "<!--INTERNAL-->": AX.internal_html(AI.INTERNAL, lambda k: f"{CIRC[NO[k]]} {html.escape(PART[k][1])}", easy=LT.INTERNAL_EASY),
              "<!--APPENDIX-->": apx,
              "{{LPOSTER_W}}": str(lpw), "{{LPOSTER_H}}": str(lfig + 82), "{{LFIG_H}}": str(lfig - 2),
              "{{SPOSTER_W}}": str(spw), "{{SPOSTER_H}}": str(sfig + 62), "{{SFIG_H}}": str(sfig - 2),
              "{{NLC}}": str(len(LC.CARDS)), "{{NLA}}": str(len(LC.ARROWS)), "{{NLB}}": str(len(LC.LAYERS)), "{{NLIN}}": str(len(ALN.LINEAGE)), "{{NHOP}}": str(nhop),
              "{{NCAU}}": str(len(ALN.CAUTION)), "{{NINT}}": str(len(AI.INTERNAL))})
    rep = {**ex, "<!--SVG-->": fig, "<!--SVG_OVERVIEW-->": figo, "<!--PARTS-->": part_cards(), "<!--LINES-->": line_rows(routed),
           "{{NP}}": str(len(PART)), "{{NL}}": str(len(L)), "{{POSTER_W}}": str(pw), "{{POSTER_H}}": str(round(pw * fh / fw + 80)),
           "{{FIG_H}}": str(round(pw * fh / fw) - 4), "{{NDRAWN}}": str(len(routed)), "{{NTAG}}": str(len(L) - len(routed))}
    for k, v in rep.items():
        assert k in s, k
        s = s.replace(k, v)
    secno = {}

    def num(m):
        secno[m.group(1)] = len(secno) + 1 + sec_offset
        return f"{m.group(0)}{secno[m.group(1)]}. "
    s = re.sub(r'<h2 id="([^"]+)"(?: class="[^"]*")?>', num, s)
    s = re.sub(r"\{sec:(\w+)\}", lambda m: str(secno[m.group(1)]), s)
    s = sub(s)
    left = re.findall(r"\{(?:n|nn|c|a|sec):\w+\}|\{\{\w+\}\}|<!--[A-Z_]+-->", s)
    assert not left, left
    ids = collections.Counter(re.findall(r'id="([^"]+)"', s))
    dup = [k for k, v in ids.items() if v > 1]
    assert not dup, f"중복 id: {dup}"
    miss = sorted({h for h in re.findall(r'href="#([^"]+)"', s)} - set(ids))
    assert not miss, f"없는 앵커: {miss}"
    s = re.sub(r'(<table class="tbl">\s*)(<tr>(?:(?!</tr>).)*?<th>.*?</tr>)', lambda m: m.group(1) + "<thead>" + m.group(2) + "</thead>", s, flags=re.S)
    if out is None:
        return s
    out.write_text(s, encoding="utf-8")
    print(f"HTML {out.name} {len(s.encode())} bytes · 부품 {len(PART)} · 연결 {len(L)} (그림에 선 {len(routed)}, 작은 표 {len(L) - len(routed)}) · 마스터 번호 대조 {nmaster}개 일치 · 그림 {fw}x{fh:.0f}")


def build_pdf():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.goto(OUT_HTML.as_uri(), wait_until="networkidle")
        pg.evaluate("document.querySelectorAll('details').forEach(d => d.open = true)")
        pg.evaluate("document.fonts.ready")
        pg.wait_for_timeout(800)
        pg.pdf(path=str(OUT_PDF), prefer_css_page_size=True, print_background=True,
               display_header_footer=True, header_template="<span></span>",
               footer_template='<div style="font-size:8px;color:#8a949b;width:100%;text-align:center;font-family:sans-serif"><span class="pageNumber"></span> / <span class="totalPages"></span></div>')
        b.close()
    print("PDF", OUT_PDF.name, OUT_PDF.stat().st_size, "bytes")


if __name__ == "__main__":
    import master_build
    master_build.build_html()
    if "--html" not in sys.argv:
        master_build.build_pdf()
