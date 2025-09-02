from flask import Flask, render_template, request

app = Flask(__name__)

# Simple estimation logic for compute and memory (placeholder)
def estimate_resources(model_size_gb, dataset_size_gb, batch_size, epochs):
    # Example formulas (not accurate, for demonstration)
    memory_required_gb = model_size_gb * 2 + batch_size * 0.01
    compute_required_gpu_hours = dataset_size_gb * epochs * 0.5 / batch_size
    return memory_required_gb, compute_required_gpu_hours

@app.route('/', methods=['GET', 'POST'])
def index():
    result = None
    if request.method == 'POST':
        try:
            model_size_gb = float(request.form['model_size_gb'])
            dataset_size_gb = float(request.form['dataset_size_gb'])
            batch_size = int(request.form['batch_size'])
            epochs = int(request.form['epochs'])
            memory, compute = estimate_resources(model_size_gb, dataset_size_gb, batch_size, epochs)
            result = {
                'memory': round(memory, 2),
                'compute': round(compute, 2)
            }
        except Exception as e:
            result = {'error': str(e)}
    return render_template('index.html', result=result)

if __name__ == '__main__':
    app.run(debug=True)
