def _stats(values):
    if not values:
        return {"min": None, "max": None, "media": None}
    return {
        "min": min(values),
        "max": max(values),
        "media": sum(values) / len(values)
    }

def analisar(logs):
    if not logs:
        return {"erro": "sem dados"}

    temps = [float(l["temperatura"]) for l in logs]
    umis = [float(l["umidade"]) for l in logs]
    tstats = _stats(temps)
    ustats = _stats(umis)

    def spikes(vs, thr=2.5):
        if len(vs) < 5:
            return []
        m = sum(vs)/len(vs)
        var = sum((x-m)*(x-m) for x in vs)/len(vs)
        sd = var**0.5 or 1.0
        return [i for i, x in enumerate(vs) if abs((x-m)/sd) > thr]

    return {
        "temperatura": tstats,
        "umidade": ustats,
        "spikes_temp_idx": spikes(temps),
        "spikes_umi_idx": spikes(umis)
    }
