"""Sequence baselines for TraceGap tasks T1-T3 on serialized traces.

Each example is serialized into a token sequence built only from task inputs:
the emitted calls (schema validity, run, nesting, position) and the recorded
trace (status, captured fields, which emitted call it refers to by call id,
group), plus the run outcome and mode. Tool names are not used (the benchmark's
names reveal behavior; see the paper). Two models:

  * TF-IDF (1-3 grams) + logistic regression;
  * a small transformer encoder trained from scratch (JAX), multi-task heads
    for T1, T2 and the ten T3 labels. Pretrained encoders could not be
    downloaded in our environment and are left as future work.

Settings: the official split (3 training seeds), random 80/20 splits (3 split seeds) and
leave-one-framework-out (one model per held-out framework, one seed for the
transformer). Results go to analysis/out/sequence_baselines.json.

    python analysis/sequence_baselines.py [--quick]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tracegap import tasks  # noqa: E402

sys.path.insert(0, str(ROOT / "analysis"))
from learned_baselines import load_all, split_of, valid_call  # noqa: E402

OUT = ROOT / "analysis" / "out"
MAXLEN = 256


# ------------------------------------------------------------------ serialization

def serialize(ex) -> list[str]:
    em = json.loads(ex["emissions_json"])
    rec = json.loads(ex["recorded_json"])
    idx = {e["call_id"]: i for i, e in enumerate(em)}
    groups: dict = {}
    toks = ["[MODE_" + ex["mode"] + "]"]
    oc = ex["run_outcome"]
    for o in ("completed", "cancelled", "raised"):
        if o in oc:
            toks.append(f"[OUT_{o}]")
    toks.append("[EMIT]")
    for i, e in enumerate(em):
        toks += [f"e{min(i, 40)}", "valid" if valid_call(e) else "invalid", f"run{e['run_index']}",
                 "nested" if e.get("nested") else "top"]
    toks.append("[REC]")
    for r in rec:
        ref = idx.get(r.get("call_id"))
        g = groups.setdefault(r.get("group"), len(groups))
        toks += [f"r{min(ref, 40)}" if ref is not None else "r?", f"st_{r['status']}",
                 "out" if r.get("output") is not None else "noout",
                 "err" if r.get("error") else "noerr",
                 "args" if r.get("args") is not None else "noargs",
                 "id" if r.get("call_id") else "noid", f"g{min(g, 9)}"]
    return toks[:MAXLEN]


def labels(ex):
    y1 = 0 if ex["label_complete"] else 1   # positive = defect
    y2 = 0 if ex["label_faithful"] else 1
    y3 = [1 if d in ex["label_defects"] else 0 for d in tasks.DEFECTS]
    return y1, y2, y3


def to_preds(test, p1, p2, p3):
    out = {}
    for e, a, b, c in zip(test, p1, p2, p3):
        out[e["id"]] = {"complete": not bool(a), "faithful": not bool(b),
                        "defects": [d for d, v in zip(tasks.DEFECTS, c) if v]}
    return out


def evaluate(test, preds):
    m = tasks.evaluate(test, preds)
    return {k: v for k, v in m.items() if k != "T4_reconstruction"}


# ------------------------------------------------------------------ TF-IDF + LR

def tfidf_lr(train, test, seed=0):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression

    vec = TfidfVectorizer(tokenizer=str.split, token_pattern=None, lowercase=False, ngram_range=(1, 3),
                          min_df=2, sublinear_tf=True)
    Xtr = vec.fit_transform([" ".join(serialize(e)) for e in train])
    Xte = vec.transform([" ".join(serialize(e)) for e in test])
    Y = [labels(e) for e in train]

    def fit(y):
        y = np.array(y)
        if len(set(y)) < 2:
            return np.full(Xte.shape[0], y[0])
        return LogisticRegression(max_iter=3000, C=4.0, class_weight="balanced", random_state=seed).fit(Xtr, y).predict(Xte)

    p1 = fit([y[0] for y in Y])
    p2 = fit([y[1] for y in Y])
    p3 = np.stack([fit([y[2][j] for y in Y]) for j in range(len(tasks.DEFECTS))], axis=1)
    return to_preds(test, p1, p2, p3)


# ------------------------------------------------------------------ transformer (JAX)

def transformer(train, test, seed=0, epochs=6, d=64, heads=4, layers=2, lr=2e-3, batch=64):
    import jax
    import jax.numpy as jnp
    import optax

    vocab = {"[PAD]": 0, "[CLS]": 1, "[UNK]": 2}
    for e in train:
        for t in serialize(e):
            vocab.setdefault(t, len(vocab))

    def encode(ex):
        ids = [1] + [vocab.get(t, 2) for t in serialize(ex)][: MAXLEN - 1]
        return ids + [0] * (MAXLEN - len(ids))

    Xtr = np.array([encode(e) for e in train], dtype=np.int32)
    Xte = np.array([encode(e) for e in test], dtype=np.int32)
    Ytr = [labels(e) for e in train]
    y1 = np.array([y[0] for y in Ytr], dtype=np.float32)
    y2 = np.array([y[1] for y in Ytr], dtype=np.float32)
    y3 = np.array([y[2] for y in Ytr], dtype=np.float32)
    # class-balanced positive weights (clipped)
    def pw(y):
        p = y.mean(axis=0)
        return np.clip((1 - p) / np.maximum(p, 1e-3), 1.0, 20.0).astype(np.float32)
    w1, w2, w3 = pw(y1), pw(y2), pw(y3)

    key = jax.random.PRNGKey(seed)
    V = len(vocab)
    nl = len(tasks.DEFECTS)

    def init(key):
        ks = jax.random.split(key, 6 + 6 * layers)
        s = 0.02
        p = {"emb": jax.random.normal(ks[0], (V, d)) * s, "pos": jax.random.normal(ks[1], (MAXLEN, d)) * s,
             "out": jax.random.normal(ks[2], (d, 2 + nl)) * s, "out_b": jnp.zeros(2 + nl), "layers": []}
        for i in range(layers):
            k = ks[6 + 6 * i: 12 + 6 * i]
            p["layers"].append({
                "qkv": jax.random.normal(k[0], (d, 3 * d)) * s, "o": jax.random.normal(k[1], (d, d)) * s,
                "f1": jax.random.normal(k[2], (d, 4 * d)) * s, "f1b": jnp.zeros(4 * d),
                "f2": jax.random.normal(k[3], (4 * d, d)) * s, "f2b": jnp.zeros(d),
                "ln1": jnp.ones(d), "ln1b": jnp.zeros(d), "ln2": jnp.ones(d), "ln2b": jnp.zeros(d)})
        return p

    def ln(x, g, b):
        m = x.mean(-1, keepdims=True)
        v = ((x - m) ** 2).mean(-1, keepdims=True)
        return (x - m) / jnp.sqrt(v + 1e-5) * g + b

    def forward(p, x):
        mask = (x > 0)
        h = p["emb"][x] + p["pos"][None]
        B, T, _ = h.shape
        for L in p["layers"]:
            a = ln(h, L["ln1"], L["ln1b"])
            q, k_, v = jnp.split(a @ L["qkv"], 3, axis=-1)
            q = q.reshape(B, T, heads, d // heads).transpose(0, 2, 1, 3)
            k_ = k_.reshape(B, T, heads, d // heads).transpose(0, 2, 1, 3)
            v = v.reshape(B, T, heads, d // heads).transpose(0, 2, 1, 3)
            att = (q @ k_.transpose(0, 1, 3, 2)) / jnp.sqrt(d // heads)
            att = jnp.where(mask[:, None, None, :], att, -1e9)
            att = jax.nn.softmax(att, axis=-1)
            o = (att @ v).transpose(0, 2, 1, 3).reshape(B, T, d)
            h = h + o @ L["o"]
            f = ln(h, L["ln2"], L["ln2b"])
            h = h + jax.nn.gelu(f @ L["f1"] + L["f1b"]) @ L["f2"] + L["f2b"]
        cls = h[:, 0]
        return cls @ p["out"] + p["out_b"]

    def wbce(logit, y, w):
        return -(w * y * jax.nn.log_sigmoid(logit) + (1 - y) * jax.nn.log_sigmoid(-logit))

    def loss(p, x, a, b, c):
        z = forward(p, x)
        return (wbce(z[:, 0], a, w1).mean() + wbce(z[:, 1], b, w2).mean() + wbce(z[:, 2:], c, w3).mean())

    params = init(key)
    steps = epochs * int(np.ceil(len(Xtr) / batch))
    opt = optax.adamw(optax.warmup_cosine_decay_schedule(0.0, lr, max(1, steps // 20), steps), weight_decay=0.01)
    state = opt.init(params)

    @jax.jit
    def step(p, s, x, a, b, c):
        l, g = jax.value_and_grad(loss)(p, x, a, b, c)
        u, s = opt.update(g, s, p)
        return optax.apply_updates(p, u), s, l

    rng = np.random.default_rng(seed)
    for _ in range(epochs):
        perm = rng.permutation(len(Xtr))
        for i in range(0, len(perm), batch):
            j = perm[i:i + batch]
            if len(j) < batch:  # keep shapes static for jit
                j = np.concatenate([j, perm[: batch - len(j)]])
            params, state, _ = step(params, state, Xtr[j], y1[j], y2[j], y3[j])

    fwd = jax.jit(forward)
    zs = []
    for i in range(0, len(Xte), 256):
        xb = Xte[i:i + 256]
        n = len(xb)
        if n < 256:
            xb = np.concatenate([xb, np.zeros((256 - n, MAXLEN), dtype=np.int32)])
        zs.append(np.asarray(fwd(params, xb))[:n])
    z = np.concatenate(zs)
    return to_preds(test, z[:, 0] > 0, z[:, 1] > 0, z[:, 2:] > 0)


# ------------------------------------------------------------------ experiments

def summarize(runs):
    keys = [("T1_completeness", "defect_f1"), ("T1_completeness", "balanced_accuracy"),
            ("T2_fidelity", "defect_f1"), ("T2_fidelity", "balanced_accuracy"),
            ("T3_defects", "micro_f1"), ("T3_defects", "macro_f1")]
    out = {}
    for t, m in keys:
        v = np.array([r[t][m] for r in runs])
        out[f"{t}.{m}"] = {"mean": float(v.mean()), "std": float(v.std(ddof=0)), "n": len(v)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--only", choices=["official", "random", "lofo"], nargs="*")
    a = ap.parse_args()
    allx = load_all()
    train = [e for e in allx if split_of(e["framework"]) == "train"]
    test = [e for e in allx if split_of(e["framework"]) == "test"]
    seeds = [0] if a.quick else [0, 1, 2]
    epochs = 3 if a.quick else 6
    path = OUT / "sequence_baselines.json"
    res = json.loads(path.read_text()) if path.exists() else {}
    todo = a.only or ["official", "random", "lofo"]

    if "official" in todo:
        t0 = time.time()
        res["official"] = {
            "tfidf_lr": summarize([evaluate(test, tfidf_lr(train, test, s)) for s in seeds[:1]]),
            "transformer": summarize([evaluate(test, transformer(train, test, s, epochs=epochs)) for s in seeds]),
        }
        print("official", json.dumps(res["official"], indent=0)[:1500], f"{time.time() - t0:.0f}s", flush=True)
        path.write_text(json.dumps(res, indent=1))

    if "random" in todo:
        runs_t, runs_x = [], []
        for s in seeds:
            rng = np.random.default_rng(100 + s)
            perm = rng.permutation(len(allx))
            cut = int(0.8 * len(allx))
            tr = [allx[i] for i in perm[:cut]]
            te = [allx[i] for i in perm[cut:]]
            runs_x.append(evaluate(te, tfidf_lr(tr, te, s)))
            runs_t.append(evaluate(te, transformer(tr, te, s, epochs=epochs)))
            print("random seed", s, flush=True)
        res["random"] = {"tfidf_lr": summarize(runs_x), "transformer": summarize(runs_t)}
        path.write_text(json.dumps(res, indent=1))

    if "lofo" in todo:
        lofo = {}
        for fw in sorted({e["framework"] for e in allx}):
            tr = [e for e in allx if e["framework"] != fw]
            te = [e for e in allx if e["framework"] == fw]
            lofo[fw] = {
                "tfidf_lr": summarize([evaluate(te, tfidf_lr(tr, te, 0))]),
                "transformer": summarize([evaluate(te, transformer(tr, te, s, epochs=epochs)) for s in seeds[:1]]),
            }
            print("lofo", fw, flush=True)
            res["lofo"] = lofo
            path.write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
