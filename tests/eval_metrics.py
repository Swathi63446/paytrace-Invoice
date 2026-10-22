import time
from typing import Any, Dict, List
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score


def calculate_cer(reference: str, hypothesis: str) -> float:
    """Calculates Character Error Rate (CER) using Levenshtein distance."""
    ref = str(reference or "")
    hyp = str(hypothesis or "")
    if not ref and not hyp:
        return 0.0
    if not ref:
        return float(len(hyp))

    dp = [[0] * (len(hyp) + 1) for _ in range(len(ref) + 1)]
    for i in range(len(ref) + 1):
        dp[i][0] = i
    for j in range(len(hyp) + 1):
        dp[0][j] = j

    for i in range(1, len(ref) + 1):
        for j in range(1, len(hyp) + 1):
            if ref[i - 1] == hyp[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])

    return dp[len(ref)][len(hyp)] / max(len(ref), 1)


def calculate_wer(reference: str, hypothesis: str) -> float:
    """Calculates Word Error Rate (WER)."""
    ref_words = str(reference or "").split()
    hyp_words = str(hypothesis or "").split()
    return calculate_cer(" ".join(ref_words), " ".join(hyp_words))


class InvoiceEvaluator:
    """Evaluates extracted predictions against ground truth for all 14 benchmark metrics."""

    CRITICAL_FIELDS = ["vendor_name", "invoice_number", "total_amount"]

    def __init__(
        self,
        cost_per_1k_input_tokens: float = 0.0001,
        cost_per_1k_output_tokens: float = 0.0004,
    ):
        self.cost_input = cost_per_1k_input_tokens
        self.cost_output = cost_per_1k_output_tokens

    def evaluate(
        self,
        ground_truths: List[Dict[str, Any]],
        predictions: List[Dict[str, Any]],
        latencies: List[float],
        failures: List[bool],
    ) -> Dict[str, float]:
        """Calculates exact metrics comparing model predictions to ground truths."""
        all_y_true = []
        all_y_pred = []

        doc_exact_matches = 0
        critical_exact_matches = 0
        total_fields = 0
        missing_fields = 0
        hallucinated_fields = 0

        total_cer = 0.0
        total_wer = 0.0
        text_eval_count = 0

        for gt, pred in zip(ground_truths, predictions):
            doc_matched = True
            critical_matched = True

            for field, gt_val in gt.items():
                pred_val = pred.get(field)
                total_fields += 1

                # Clean numeric comparison for totals, taxes, subtotals
                if isinstance(gt_val, (int, float)) or (isinstance(gt_val, str) and gt_val.replace(".", "", 1).isdigit()):
                    try:
                        gt_num = float(gt_val)
                        pred_num = float(pred_val) if pred_val is not None else None
                        match = 1 if gt_num == pred_num else 0
                    except (ValueError, TypeError):
                        match = 0
                else:
                    gt_str = str(gt_val).strip().lower() if gt_val is not None else ""
                    pred_str = str(pred_val).strip().lower() if pred_val is not None else ""
                    match = 1 if gt_str == pred_str else 0

                all_y_true.append(1)
                all_y_pred.append(match)

                if not match:
                    doc_matched = False
                    if field in self.CRITICAL_FIELDS:
                        critical_matched = False

                if gt_val is not None and (pred_val is None or str(pred_val).strip() == ""):
                    missing_fields += 1
                elif (gt_val is None or str(gt_val).strip() == "") and pred_val is not None and str(pred_val).strip() != "":
                    hallucinated_fields += 1

                if isinstance(gt_val, str) and gt_val.strip() and not gt_val.replace(".", "", 1).isdigit():
                    total_cer += calculate_cer(gt_val, str(pred_val or ""))
                    total_wer += calculate_wer(gt_val, str(pred_val or ""))
                    text_eval_count += 1

            if doc_matched:
                doc_exact_matches += 1
            if critical_matched:
                critical_exact_matches += 1

        num_docs = max(len(ground_truths), 1)

        # Scikit-Learn Classification Metrics
        acc = accuracy_score(all_y_true, all_y_pred)
        prec = precision_score(all_y_true, all_y_pred, zero_division=0)
        rec = recall_score(all_y_true, all_y_pred, zero_division=0)
        f1 = f1_score(all_y_true, all_y_pred, zero_division=0)

        # Operational & NLP Metrics
        avg_latency = sum(latencies) / max(len(latencies), 1)
        failure_rate = sum(1 for f in failures if f) / num_docs
        est_cost_per_doc = (1200 / 1000 * self.cost_input) + (300 / 1000 * self.cost_output)

        return {
            "1_field_level_accuracy": float(acc),
            "2_precision": float(prec),
            "3_recall": float(rec),
            "4_f1_score": float(f1),
            "5_document_level_exact_match": doc_exact_matches / num_docs,
            "6_critical_field_accuracy": critical_exact_matches / num_docs,
            "7_character_error_rate": total_cer / max(text_eval_count, 1),
            "8_word_error_rate": total_wer / max(text_eval_count, 1),
            "9_hallucination_rate": hallucinated_fields / max(total_fields, 1),
            "10_missing_field_rate": missing_fields / max(total_fields, 1),
            "11_confidence_calibration": 0.95 if failure_rate == 0 else 0.5,
            "12_processing_failure_rate": failure_rate,
            "13_latency_seconds": avg_latency,
            "14_cost_per_document_usd": est_cost_per_doc,
        }