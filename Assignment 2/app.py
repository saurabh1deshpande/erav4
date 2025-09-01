from flask import Flask, render_template_string, request
import math

app = Flask(__name__)

# --- Helper to parse model size like "7B", "350M" ---
def parse_params(val: str) -> float:
    val = val.strip().upper()
    if val.endswith("B"):
        return float(val[:-1]) * 1e9
    elif val.endswith("M"):
        return float(val[:-1]) * 1e6
    else:
        return float(val)

# --- HTML Template with Bootstrap Styling & Sticky Values ---
TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>LLM Fine-tuning Calculator</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background: #f4f6f9; }
        .card { border-radius: 16px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
        .container { max-width: 900px; margin-top: 40px; }
        h2 { font-weight: 600; margin-bottom: 20px; }
        label { font-weight: 500; margin-top: 10px; }
        .result-card { background: #ffffff; border-left: 5px solid #007bff; }
        .section-title { margin-top: 15px; font-weight: 600; }
    </style>
</head>
<body>
    <div class="container">
        <div class="card p-4">
            <h2>LLM Fine-tuning Resource Calculator</h2>
            <form method="post" class="row g-3">
                <div class="col-md-6">
                    <label>Model Parameters</label>
                    <input type="text" class="form-control" name="params" 
                           placeholder="e.g. 7B, 350M, 7e9" 
                           value="{{ form_data.params if form_data else '' }}" required>
                </div>
                <div class="col-md-6">
                    <label>Fine-tuning Method</label>
                    <select name="method" class="form-select">
                        <option value="full"  {% if form_data and form_data.method == 'full' %}selected{% endif %}>Full Fine-tuning</option>
                        <option value="lora"  {% if form_data and form_data.method == 'lora' %}selected{% endif %}>LoRA</option>
                        <option value="qlora" {% if form_data and form_data.method == 'qlora' %}selected{% endif %}>QLoRA</option>
                    </select>
                </div>
                <div class="col-md-6">
                    <label>Precision</label>
                    <select name="precision" class="form-select">
                        <option value="fp16" {% if form_data and form_data.precision == 'fp16' %}selected{% endif %}>FP16 / BF16</option>
                        <option value="fp32" {% if form_data and form_data.precision == 'fp32' %}selected{% endif %}>FP32</option>
                        <option value="int8" {% if form_data and form_data.precision == 'int8' %}selected{% endif %}>8-bit</option>
                        <option value="int4" {% if form_data and form_data.precision == 'int4' %}selected{% endif %}>4-bit</option>
                    </select>
                </div>
                <div class="col-md-6">
                    <label>Sequence Length (tokens)</label>
                    <input type="number" class="form-control" name="seq_len" value="{{ form_data.seq_len if form_data else 2048 }}" required>
                </div>
                <div class="col-md-6">
                    <label>Batch Size</label>
                    <input type="number" class="form-control" name="batch_size" value="{{ form_data.batch_size if form_data else 4 }}" required>
                </div>
                <div class="col-md-6">
                    <label>GPU Memory Capacity (GB per GPU)</label>
                    <input type="number" class="form-control" name="gpu_capacity" value="{{ form_data.gpu_capacity if form_data else 80 }}" required>
                </div>
                <div class="col-12">
                    <button type="submit" class="btn btn-primary px-4">Calculate</button>
                </div>
            </form>
        </div>

        {% if result %}
        <div class="card p-4 mt-4 result-card">
            <h4>Estimated Requirements</h4>
            <div class="section-title">🔹 Training</div>
            <ul class="list-group list-group-flush mb-3">
                <li class="list-group-item"><b>Total GPU Memory Needed:</b> {{ result['train_mem'] }} GB</li>
                <li class="list-group-item"><b>GPUs Required:</b> {{ result['train_gpus'] }}</li>
                <li class="list-group-item"><b>Compute per token:</b> {{ result['train_flops'] | scientific }} FLOPs</li>
            </ul>
            <div class="section-title">🔹 Inference</div>
            <ul class="list-group list-group-flush">
                <li class="list-group-item"><b>Total GPU Memory Needed:</b> {{ result['infer_mem'] }} GB</li>
                <li class="list-group-item"><b>GPUs Required:</b> {{ result['infer_gpus'] }}</li>
                <li class="list-group-item"><b>Compute per token:</b> {{ result['infer_flops'] | scientific }} FLOPs</li>
            </ul>
        </div>
        {% endif %}
    </div>
</body>
</html>
"""

@app.template_filter('scientific')
def scientific_notation(value):
    return "{:.2e}".format(value)

@app.route("/", methods=["GET", "POST"])
def index():
    result = None
    form_data = None

    if request.method == "POST":
        form_data = request.form
        params = parse_params(form_data["params"])
        method = form_data["method"]
        precision = form_data["precision"]
        seq_len = int(form_data["seq_len"])
        batch_size = int(form_data["batch_size"])
        gpu_capacity = int(form_data["gpu_capacity"])

        # Bytes per param
        if precision == "fp32":
            bytes_per_param = 4
        elif precision == "fp16":
            bytes_per_param = 2
        elif precision == "int8":
            bytes_per_param = 1
        elif precision == "int4":
            bytes_per_param = 0.5
        else:
            bytes_per_param = 2

        # --- Training Memory ---
        param_mem = (params * bytes_per_param) / 1e9
        if method == "full":
            opt_mem = param_mem * 2
            act_mem = param_mem * (seq_len / 2048) * (batch_size / 4)
            train_mem = param_mem + opt_mem + act_mem
        elif method == "lora":
            train_mem = (param_mem * 0.25) + 2
        else:  # qlora
            train_mem = (param_mem * 0.15) + 1.5
        train_gpus = math.ceil(train_mem / gpu_capacity)
        train_flops = 6 * params

        # --- Inference Memory ---
        infer_mem = param_mem + (param_mem * 0.2) * (seq_len / 2048) * (batch_size / 1)
        infer_gpus = math.ceil(infer_mem / gpu_capacity)
        infer_flops = 2 * params

        result = {
            "train_mem": round(train_mem, 2),
            "train_gpus": train_gpus,
            "train_flops": train_flops,
            "infer_mem": round(infer_mem, 2),
            "infer_gpus": infer_gpus,
            "infer_flops": infer_flops
        }

    return render_template_string(TEMPLATE, result=result, form_data=form_data)


if __name__ == "__main__":
    app.run(debug=True)
