def reconstruct(skeleton, translations):
    for seg_id, text in translations.items():
        skeleton = skeleton.replace(f"$(ID:{seg_id})", text)
    return skeleton