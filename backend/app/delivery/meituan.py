import re
from statistics import median

ETA_RANGE = re.compile(r"(\d+)\s*-\s*(\d+)\s*分钟")
ETA_FAST = re.compile(r"最快\s*(\d+)\s*分钟")
ETA_SINGLE = re.compile(r"(\d+)\s*分钟")
FEE = re.compile(r"配送\s*约?\s*¥?\s*([\d.]+)")


def _parse_eta(caption: str) -> tuple[int, int] | None:
    match = ETA_RANGE.search(caption)
    if match:
        return int(match.group(1)), int(match.group(2))
    match = ETA_FAST.search(caption) or ETA_SINGLE.search(caption)
    if match:
        value = int(match.group(1))
        return value, value
    return None


def _parse_fee(caption: str) -> float | None:
    if "免配送费" in caption:
        return 0.0
    match = FEE.search(caption)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


def extract_probe(items: list[dict]) -> dict:
    captions = [item.get("caption", "") for item in items if item.get("caption")]
    address = None
    for caption in captions:
        if caption.startswith("地址:"):
            address = caption.split("地址:", 1)[1].split(",", 1)[0].strip()
            break
    cards = [caption for caption in captions if "起送" in caption and "分钟" in caption]
    etas: list[tuple[int, int]] = []
    fees: list[float] = []
    for caption in cards[:8]:
        eta = _parse_eta(caption)
        if eta:
            etas.append(eta)
        fee = _parse_fee(caption)
        if fee is not None:
            fees.append(fee)
    if not etas:
        raise ValueError("no ETA found in accessibility tree")
    eta_low = int(median([item[0] for item in etas]))
    eta_high = int(median([item[1] for item in etas]))
    fee = round(median(fees), 2) if fees else None
    confidence = 0.9 if address and len(cards) >= 3 else 0.5
    return {
        "address_label": address,
        "eta_min_low": eta_low,
        "eta_min_high": eta_high,
        "fee": fee,
        "merchant_count": len(cards),
        "confidence": confidence,
        "raw_text": "\n".join([f"地址: {address or '未知'}"] + cards[:8]),
    }
