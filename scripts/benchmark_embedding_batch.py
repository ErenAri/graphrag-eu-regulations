import argparse
import json
from time import perf_counter
from typing import Any

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="benchmark-embedding-batch")
    parser.add_argument("--samples", type=int, default=512, help="Number of synthetic texts.")
    parser.add_argument(
        "--words-per-sample",
        type=int,
        default=96,
        help="Approximate tokenized word count per synthetic text.",
    )
    parser.add_argument(
        "--batch-sizes",
        default="8,16,24,32,48,64",
        help="Comma-separated batch sizes to benchmark.",
    )
    parser.add_argument(
        "--device",
        default="auto",
        help="Embedding device override (auto, cuda, cpu, cuda:0, ...).",
    )
    parser.add_argument(
        "--model",
        default="BAAI/bge-m3",
        help="SentenceTransformer model ID.",
    )
    return parser.parse_args()


def parse_batch_sizes(raw: str) -> list[int]:
    values = sorted({int(item.strip()) for item in raw.split(",") if item.strip()})
    if not values or any(value <= 0 for value in values):
        raise ValueError("batch_sizes_must_be_positive")
    return values


def resolve_device(requested: str) -> str:
    if requested != "auto":
        return requested
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"


def synthetic_corpus(samples: int, words_per_sample: int) -> list[str]:
    if samples <= 0:
        raise ValueError("samples_must_be_positive")
    if words_per_sample <= 0:
        raise ValueError("words_per_sample_must_be_positive")
    base_words = [
        "Regulatory",
        "compliance",
        "obligations",
        "for",
        "payment",
        "institutions",
        "require",
        "risk",
        "governance",
        "incident",
        "reporting",
        "prudential",
        "controls",
        "cross-border",
        "oversight",
        "consumer",
        "protection",
        "cybersecurity",
        "assurance",
        "documentation",
    ]
    text: list[str] = []
    while len(text) < words_per_sample:
        text.extend(base_words)
    sentence = " ".join(text[:words_per_sample])
    return [f"{sentence} sample-index-{index}" for index in range(samples)]


def benchmark_batch(
    model: Any,
    texts: list[str],
    batch_size: int,
    device: str,
) -> dict[str, Any]:
    torch = None
    peak_vram_mib: float | None = None
    peak_vram_ratio: float | None = None
    if device.startswith("cuda"):
        import torch as torch_module

        torch = torch_module
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats()

    start = perf_counter()
    model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    if torch is not None:
        torch.cuda.synchronize()
    elapsed = perf_counter() - start
    throughput = len(texts) / elapsed if elapsed > 0 else 0.0

    if torch is not None:
        peak_bytes = float(torch.cuda.max_memory_allocated())
        total_bytes = float(torch.cuda.get_device_properties(0).total_memory)
        peak_vram_mib = peak_bytes / (1024 * 1024)
        peak_vram_ratio = peak_bytes / total_bytes if total_bytes > 0 else None

    return {
        "batch_size": batch_size,
        "ok": True,
        "seconds": round(elapsed, 4),
        "throughput_texts_per_second": round(throughput, 2),
        "peak_vram_mib": round(peak_vram_mib, 2) if peak_vram_mib is not None else None,
        "peak_vram_ratio": round(peak_vram_ratio, 4) if peak_vram_ratio is not None else None,
    }


def recommend(results: list[dict[str, Any]]) -> int | None:
    successful = [result for result in results if result.get("ok")]
    if not successful:
        return None
    conservative_headroom = [
        result
        for result in successful
        if result["peak_vram_ratio"] is None or result["peak_vram_ratio"] <= 0.75
    ]
    standard_headroom = [
        result
        for result in successful
        if result["peak_vram_ratio"] is None or result["peak_vram_ratio"] <= 0.85
    ]
    candidate_pool = conservative_headroom or standard_headroom or successful
    best = max(
        candidate_pool,
        key=lambda result: (
            float(result["throughput_texts_per_second"]),
            -float(result["peak_vram_ratio"] or 0.0),
            int(result["batch_size"]),
        ),
    )
    return int(best["batch_size"])


def main() -> None:
    args = parse_args()
    batch_sizes = parse_batch_sizes(args.batch_sizes)
    device = resolve_device(args.device)
    texts = synthetic_corpus(args.samples, args.words_per_sample)

    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(args.model, device=device)
    results: list[dict[str, Any]] = []
    for batch_size in batch_sizes:
        try:
            result = benchmark_batch(model, texts, batch_size, device)
            results.append(result)
        except RuntimeError as exc:
            message = str(exc)
            if "out of memory" in message.lower():
                results.append({"batch_size": batch_size, "ok": False, "error": "cuda_out_of_memory"})
                try:
                    import torch

                    if device.startswith("cuda"):
                        torch.cuda.empty_cache()
                except Exception:
                    pass
                continue
            raise

    output = {
        "model": args.model,
        "device": device,
        "samples": args.samples,
        "words_per_sample": args.words_per_sample,
        "results": results,
        "recommended_batch_size": recommend(results),
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
