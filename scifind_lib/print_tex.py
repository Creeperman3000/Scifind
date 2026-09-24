import re

PAPERS_MM = {
    "letter": (215.9, 279.4),
    "legal": (215.9, 355.6),
    "tabloid": (279.4, 431.8),
    "a0": (841.0, 1189.0),
    "a1": (594.0, 841.0),
    "a2": (420.0, 594.0),
    "a3": (297.0, 420.0),
    "a4": (210.0, 297.0),
    "a5": (148.0, 210.0),
    "a6": (105.0, 148.0),
}

_TEX_SPECIALS = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_\allowbreak{}",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def tex_escape(text):
    return "".join(_TEX_SPECIALS.get(ch, ch) for ch in text or "")


_BLOCKED_TEX_CMDS = frozenset({
    "input", "include", "includeonly", "openin", "openout",
    "closein", "closeout", "read", "write", "immediate",
    "newread", "newwrite", "lstinputlisting", "inputminted", "includepdf",
    "def", "edef", "gdef", "xdef", "let", "futurelet",
    "csname", "endcsname", "catcode", "chardef",
    "newcommand", "renewcommand", "providecommand",
    "directlua", "shellescape",
})

_CMD_RE = re.compile(r"\\[a-zA-Z]+")


def tex_math(fragment):
    return _CMD_RE.sub(
        lambda m: "?" if m.group(0)[1:].lower() in _BLOCKED_TEX_CMDS else m.group(0),
        fragment or "")


def _tabular_page(cells, cols, col_w, cell_h, *, rules, tabcolsep):
    cell = ">{\\centering\\arraybackslash}m{%.2fmm}" % col_w
    inner = "|".join([cell] * cols)
    spec = "@{}|" + inner + "|@{}" if rules else "@{}" + cell * cols + "@{}"
    empty = "\\parbox[c][%.2fmm][c]{\\linewidth}{\\mbox{}}" % cell_h
    out = ["{\\renewcommand{\\arraystretch}{1.00}\\setlength{\\tabcolsep}{%.2fmm}"
           "\\setlength{\\extrarowheight}{0pt}" % tabcolsep,
           "\\noindent\\begin{tabular}{%s}" % spec]
    if rules:
        out.append("\\hline")
    for i in range(0, len(cells), cols):
        row = (list(cells[i:i + cols]) + [None] * cols)[:cols]
        out.append(" & ".join(empty if c is None else c for c in row) + " \\\\")
        if rules:
            out.append("\\hline")
    return "\n".join(out) + "\n\\end{tabular}}"


def build_print_tex(formulas, quantities, *, layout, cols, rows=16, borders, paper, area_w, area_h):
    pw, ph = PAPERS_MM.get(paper, PAPERS_MM["a4"])
    text_w = max(10.0, min(area_w - 20.0, pw - 20.0))
    text_h = max(10.0, min(area_h - 20.0, ph - 20.0))
    left, top = max(0.0, (pw - text_w) / 2.0), max(0.0, (ph - text_h) / 2.0)
    cols, rows = max(1, min(32, int(cols))), max(1, min(32, int(rows)))
    rule_w, rule_h = (0.15 * (cols + 1), 0.15 * (rows + 1)) if borders else (0.0, 0.0)
    tabcolsep = max(0.8, min(2.0 if borders else 4.0, (text_w - rule_w - cols * 3.0) / (2.0 * cols)))
    col_w = max(3.0, (text_w - 2.0 * tabcolsep * cols - rule_w) / cols)
    # Back-card names shrink a step in narrow columns so they wrap into
    # fewer lines instead of one word per line plus downscaling.
    name_size = "\\large" if col_w >= 30.0 else ("\\normalsize" if col_w >= 20.0 else "\\small")
    cell_h = max(6.0, (text_h - rule_h) / rows)
    name_h = max(1.5, min(0.35 * cell_h, 12.0, cell_h - 4.7))
    eq_full_h, eq_split_h = max(2.0, cell_h - 3.0), max(1.5, cell_h - name_h - 3.7)
    eq_gap = max(1.0, min(4.0, 0.12 * cell_h))
    lines = [
        "\\documentclass[11pt]{extarticle}",
        "\\usepackage{fontspec}",
        "\\usepackage{amsmath}",
        "\\usepackage{unicode-math}",
        "\\usepackage[paperwidth=%.1fmm,paperheight=%.1fmm,left=%.1fmm,top=%.1fmm,"
        "textwidth=%.1fmm,textheight=%.1fmm]{geometry}" % (pw, ph, left, top, text_w, text_h),
        "\\usepackage{array}",
        "\\usepackage{graphicx}",
        "\\usepackage{adjustbox}",
        "\\usepackage{varwidth}",
        "\\usepackage{xcolor}",
        "\\usepackage{colortbl}",
        "\\usepackage{ragged2e}",
        "\\usepackage{microtype}",
        "\\setlength{\\arrayrulewidth}{0.3pt}",
        "\\arrayrulecolor{black!25}",
        "\\pagestyle{empty}",
        "\\setlength{\\parindent}{0pt}",
        "\\newsavebox{\\scifitbox}",
        "\\ExplSyntaxOn",
        "\\cs_new:Npn \\scifind_fit:nnn #1 #2 #3",
        "  {",
        "    \\sbox { \\scifitbox } { #3 }",
        "    \\dim_compare:nNnTF { \\box_wd:N \\scifitbox } < { 0.1pt }",
        "      { \\usebox { \\scifitbox } }",
        "      {",
        "        \\fp_set:Nn \\l_tmpa_fp",
        "          { \\dim_to_fp:n { #1 } / \\dim_to_fp:n { \\box_wd:N \\scifitbox } }",
        "        \\fp_set:Nn \\l_tmpb_fp",
        "          {",
        "            \\dim_to_fp:n { #2 } /",
        "            \\dim_to_fp:n { \\box_ht:N \\scifitbox + \\box_dp:N \\scifitbox }",
        "          }",
        "        \\fp_set:Nn \\l_tmpa_fp { \\fp_min:nn { \\l_tmpa_fp } { \\l_tmpb_fp } }",
        "        \\fp_set:Nn \\l_tmpa_fp { \\fp_min:nn { \\l_tmpa_fp } { 1.5 } }",
    ]
    tiers = ["0.55", "0.70", "0.85", "1.0", "1.15", "1.3", "1.5"]
    depth = 8
    lines.append(" " * depth + "\\fp_compare:nNnTF { \\l_tmpa_fp } < { %s }" % tiers[0])
    lines.append(" " * depth + "  { \\edef\\scifitscale{\\fp_use:N \\l_tmpa_fp} }")
    lines.append(" " * depth + "  {")
    for i, (threshold, scale) in enumerate(zip(tiers[1:], tiers[:-1])):
        depth += 4
        lines.append(" " * depth + "\\fp_compare:nNnTF { \\l_tmpa_fp } < { %s }" % threshold)
        lines.append(" " * depth + "  { \\def\\scifitscale{%s} }" % scale)
        if i < len(tiers) - 2:
            lines.append(" " * depth + "  {")
    lines.append(" " * (depth + 2) + "{ \\def\\scifitscale{1.5} }")
    lines.extend(" " * d + "}" for d in range(depth - 2, 6, -4))
    lines.extend([
        "        \\scalebox{\\scifitscale}{\\usebox{\\scifitbox}}",
        "      }",
        "  }",
        "\\newcommand{\\qdis}[2]{\\scifind_fit:nnn{\\linewidth - 2mm}{#1}{$\\displaystyle #2$}}",
        "\\newcommand{\\qtxt}[2]{\\scifind_fit:nnn{\\linewidth - 2mm}{#1}{$\\textstyle #2$}}",
        "\\ExplSyntaxOff",
        "\\begin{document}",
    ])

    def page(cells, mirror=False):
        cells = (list(cells) + [None] * (cols * rows))[:cols * rows]
        if mirror:
            cells = [cell for i in range(0, len(cells), cols) for cell in cells[i:i + cols][::-1]]
        return _tabular_page(cells, cols, col_w, cell_h, rules=borders, tabcolsep=tabcolsep)

    def _namebox(name_tex, slot_h, size="\\footnotesize"):
        return ("\\adjustbox{max width=\\dimexpr\\linewidth-2mm\\relax,"
                "max totalheight=%.2fmm,keepaspectratio}"
                "{\\begin{varwidth}{\\dimexpr\\linewidth-2mm\\relax}"
                "{\\Centering%s %s\\par}\\end{varwidth}}"
                % (slot_h, size, name_tex))

    def full_cell(tex, style="displaystyle"):
        cmd = "\\qdis" if style == "displaystyle" else "\\qtxt"
        return ("\\parbox[c][%.2fmm][c]{\\linewidth}{\\centering %s{%.2fmm}{%s}}"
                % (cell_h, cmd, eq_full_h, tex))

    def ref_cell(tex, name_tex):
        return ("\\parbox[c][%.2fmm][c]{\\linewidth}{\\centering \\qdis{%.2fmm}{%s}\\par\\vspace{%.1fpt}"
                "%s}" % (cell_h, eq_split_h, tex, eq_gap, _namebox(name_tex, name_h)))

    def back_cell(name_tex):
        return "\\parbox[c][%.2fmm][c]{\\linewidth}{\\centering %s}" % (cell_h, _namebox(name_tex, cell_h - 3.0, name_size))

    items = [{"name": formula.get("name") or "", "latex": formula.get("latex") or ""} for formula in formulas or []]
    for quantity in quantities or []:
        symbol, unit = quantity.get("symbol"), quantity.get("unit_latex")
        items.append({"name": quantity.get("name") or "",
                      "latex": "%s\\;(%s)" % (symbol, unit) if symbol and unit else symbol or unit or ""})
    for item in items:
        item["tex"], item["name_tex"] = tex_math(item["latex"]), tex_escape(item["name"])
    if not items:
        return "\n".join(lines + ["\\end{document}\n"])

    per_page = cols * rows
    chunks = [items[i:i + per_page] for i in range(0, len(items), per_page)]
    style = "textstyle" if layout == "l1" else None
    for ci, chunk in enumerate(chunks):
        if layout == "l3":
            lines.append(page([full_cell(item["tex"]) for item in chunk]))
            lines.append("\\clearpage")
            lines.append(page([back_cell(item["name_tex"]) for item in chunk], mirror=True))
        else:
            cells = [full_cell(item["tex"], style) if style else ref_cell(item["tex"], item["name_tex"]) for item in chunk]
            lines.append(page(cells))
        if ci < len(chunks) - 1:
            lines.append("\\clearpage")
    return "\n".join(lines + ["\\end{document}\n"])
