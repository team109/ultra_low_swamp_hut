"""Render separate Chinese and English seed-compatibility diagrams."""

import json
from itertools import groupby
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]


def major_version(version):
    parts = version.split(".")
    return parts[0] + ".x" if int(parts[0]) >= 26 else ".".join(parts[:2])


def render(language):
    catalog = json.loads((ROOT / "data/versions/compatibility.json").read_text())
    versions = catalog["search_versions"]
    chinese = language == "zh"
    left, column, padding = 160, 44, 24
    width = left + column * len(versions) + padding
    title = "沼泽小屋种子互通" if chinese else "Swamp-hut seed compatibility"
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="364" viewBox="0 0 {width} 364" role="img">',
        f"<title>{escape(title)}</title>",
        '<rect width="100%" height="100%" rx="12" fill="#f8fafc"/>',
        (
            '<g font-family="Noto Sans CJK SC, PingFang SC, Microsoft YaHei, sans-serif">'
            if chinese
            else '<g font-family="Inter, DejaVu Sans, sans-serif">'
        ),
    ]

    def text(x, y, value, size=13, color="#334155", anchor="start", weight=400):
        parts.append(
            f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" text-anchor="{anchor}" font-weight="{weight}">{escape(value)}</text>'
        )

    text(20, 30, title, 20, "#0f172a", weight=600)
    text(20, 70, "大版本" if chinese else "Major release", 12, "#64748b")
    text(20, 123, "小版本" if chinese else "Minor version", 12, "#64748b")
    major_groups = []
    for major, indices in groupby(
        range(len(versions)), key=lambda index: major_version(versions[index])
    ):
        positions = list(indices)
        major_groups.append((major, positions[0], len(positions)))
    for major_index, (major, start, length) in enumerate(major_groups):
        x, span = left + start * column, length * column
        fill = "#e2e8f0" if major_index % 2 == 0 else "#edf2f7"
        parts.append(
            f'<rect x="{x + 1}" y="47" width="{span - 2}" height="35" rx="5" fill="{fill}"/>'
        )
        text(x + span / 2, 70, major, 15, "#0f172a", "middle", 600)
        if start:
            parts.append(
                f'<path d="M{x} 42V331" stroke="#94a3b8" stroke-width="1.5" stroke-dasharray="4 4"/>'
            )
    for index, version in enumerate(versions):
        x = left + index * column
        parts.append(f"<g><title>{escape(version)}</title>")
        label_y = 105 if index % 2 == 0 else 132
        text(x + column / 2, label_y, version, 12, "#475569", "middle")
        parts.append(
            f'<path d="M{x + column / 2} {label_y + 5}V146" stroke="#cbd5e1"/>'
        )
        parts.append("</g>")
    rows = [
        ("near_generation_groups", 165, 64, "#e0edff", "#2558a0"),
        ("exact_generation_groups", 269, 52, "#d7eee7", "#17664e"),
    ]
    for key, y, height, fill, ink in rows:
        near = key == "near_generation_groups"
        if chinese:
            text(20, y + 25, "通常互通" if near else "严格互通", 17, ink, weight=600)
            text(20, y + 46, "允许局部变化" if near else "生成结果等效", 12, "#64748b")
        else:
            text(20, y + 23, "Usually" if near else "Exact", 16, ink, weight=600)
            text(
                20,
                y + 44,
                "transferable" if near else "equivalence",
                16,
                ink,
                weight=600,
            )
        flattened = [version for group in catalog[key] for version in group["versions"]]
        if flattened != versions:
            raise ValueError(f"{key} must partition releases in order")
        for group in catalog[key]:
            start = versions.index(group["versions"][0])
            length = len(group["versions"])
            x, span = left + start * column + 2, length * column - 4
            first, last = group["versions"][0], group["versions"][-1]
            parts.append(
                f'<g><title>{escape(", ".join(group["versions"]))}</title><rect x="{x}" y="{y}" width="{span}" height="{height}" rx="7" fill="{fill}" stroke="{ink}" stroke-opacity=".24"/>'
            )
            if near:
                text(x + span / 2, y + 27, first + "–" + last, 17, ink, "middle", 600)
                if chinese:
                    subtitle = "试炼密室加入前" if start == 0 else "包含试炼密室"
                else:
                    subtitle = (
                        "Before trial chambers" if start == 0 else "With trial chambers"
                    )
                text(x + span / 2, y + 49, subtitle, 12, ink, "middle")
            else:
                if length == 1:
                    text(x + span / 2, y + 31, first, 10, ink, "middle", 600)
                else:
                    text(x + span / 2, y + 22, first, 11, ink, "middle", 600)
                    text(x + span / 2, y + 39, last, 11, ink, "middle", 600)
            parts.append("</g>")
    caption = (
        "每个连续色块代表一个互通区间；虚线标记大版本分界。"
        if chinese
        else "Each bar is one compatibility group · Dashed lines mark major releases"
    )
    text(20, 350, caption, 12 if chinese else 11, "#64748b")
    parts.append("</g></svg>\n")
    target = ROOT / "docs/images" / f"version-compatibility-{language}.svg"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(parts))
    return target


if __name__ == "__main__":
    for language in ["zh", "en"]:
        print(render(language).relative_to(ROOT))
