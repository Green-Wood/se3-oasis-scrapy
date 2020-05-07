def get_keywords(paper):
    if 'keywords' not in paper:
        return None
    res = []
    for kds in paper['keywords']:
        if 'kwd' in kds and 'type' in kds and 'Author Keywords' not in kds['type']:
            res += kds['kwd']
    return res if res else None