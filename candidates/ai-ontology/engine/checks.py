"""온톨로지에 선언된 확인 조건을 관측으로 평가한다. 도메인 지식(태그·임계값)은 모두 조건 데이터에서 온다.

ctx = {"history": {tag: [(t_sec, value), ...] 오름차순}, "state": {"commands": {...}, "interlock": bool},
       "spec": {tag: {"lsl": x|None, "usl": y|None, "unit": u}}}
평가 결과는 True / False / None(판단할 관측이 없음).
"""
import operator

CMP = {">": operator.gt, ">=": operator.ge, "<": operator.lt, "<=": operator.le, "==": operator.eq, "!=": operator.ne}


def _last(ctx, tag):
    rows = ctx["history"].get(tag) or []
    return rows[-1][1] if rows else None


def _ref(ctx, tag, which):
    return (ctx["spec"].get(tag) or {}).get(which)


def _rhs(ctx, cond, default_tag=None):
    if "value" in cond:
        return cond["value"]
    return _ref(ctx, cond.get("ref_tag", default_tag), cond["ref"])


def evaluate(cond, ctx):
    if "all" in cond:
        parts = [evaluate(c, ctx) for c in cond["all"]]
        if any(p is False for p in parts):
            return False
        return None if any(p is None for p in parts) else True
    if "tag_last" in cond:
        v, r = _last(ctx, cond["tag_last"]), _rhs(ctx, cond, cond["tag_last"])
        return None if v is None or r is None else CMP[cond["cmp"]](v, r)
    if "tag_diff" in cond:
        a, b = (_last(ctx, t) for t in cond["tag_diff"])
        return None if a is None or b is None else CMP[cond["cmp"]](a - b, cond["value"])
    if "command" in cond:
        v = (ctx["state"].get("commands") or {}).get(cond["command"])
        if isinstance(v, bool):
            v = int(v)
        r = _rhs(ctx, cond)
        return None if v is None or r is None else CMP[cond["cmp"]](v, r)
    if "interlock" in cond:
        v = ctx["state"].get("interlock")
        return None if v is None else bool(v) == bool(cond["interlock"])
    if "excursion" in cond:
        tag = cond["excursion"]
        lim = _ref(ctx, tag, cond.get("above", "usl"))
        rows = ctx["history"].get(tag) or []
        if lim is None or not rows:
            return None
        above = [t for t, v in rows if v > lim]
        if not above:
            return False
        return (max(above) - min(above)) <= cond["max_s"] and rows[-1][1] < lim
    raise ValueError(f"알 수 없는 조건: {cond}")


def judge_failure_mode(fm, ctx):
    """requires 거짓 → not_applicable / refutes 참 → refuted / supports 모두 참 → supported / 그 외 unknown."""
    detail = {}
    if not fm.get("observable", True):
        return "unknown", {"reason": "센서로 확인 불가", "field_check": fm.get("field_check")}
    for c in fm.get("requires", []):
        r = evaluate(c, ctx)
        detail.setdefault("requires", []).append([c, r])
        if r is not True:
            return "not_applicable", detail
    for c in fm.get("refutes", []):
        r = evaluate(c, ctx)
        detail.setdefault("refutes", []).append([c, r])
        if r is True:
            return "refuted", detail
    sup = [evaluate(c, ctx) for c in fm.get("supports", [])]
    detail["supports"] = [[c, r] for c, r in zip(fm.get("supports", []), sup)]
    if sup and all(r is True for r in sup):
        return "supported", detail
    return "unknown", detail
