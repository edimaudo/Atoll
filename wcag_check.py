"""WCAG 2.1 contrast ratio checker - not a guess, actual relative-luminance math."""

def hex_to_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def relative_luminance(rgb):
    def channel(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)

def contrast_ratio(hex1, hex2):
    l1 = relative_luminance(hex_to_rgb(hex1))
    l2 = relative_luminance(hex_to_rgb(hex2))
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)

def check(name, fg, bg, large=False):
    ratio = contrast_ratio(fg, bg)
    threshold_aa = 3.0 if large else 4.5
    threshold_aaa = 4.5 if large else 7.0
    status = "AAA" if ratio >= threshold_aaa else ("AA" if ratio >= threshold_aa else "FAIL")
    print(f"{status:5} {ratio:5.2f}:1  {name:45} ({fg} on {bg})")
    return status != "FAIL"

if __name__ == "__main__":
    import sys
    print(f"{'':5} {'ratio':>6}  description")
    print("-" * 80)
