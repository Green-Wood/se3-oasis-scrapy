def get_keywords(paper):
    if 'keywords' not in paper:
        return None
    res = []
    for kds in paper['keywords']:
        if 'kwd' in kds and 'type' in kds and 'Author Keywords' not in kds['type']:
            res += kds['kwd']
    
    if not res:
        return None
    
    tmp = []
    for kwd in res:
        if len(kwd) > 15 and ',' in kwd:
            tmp += [x for x in kwd.split(',')]
        else:
            tmp.append(kwd)
    return tmp