import subprocess
import threading
import queue
from flask import Flask, request, jsonify
import os
import atexit
import json

app = Flask(__name__)
# A single queue to serialize all incoming requests
request_queue = queue.Queue()

# Globals for the process
melotts_process = None

# Path to the melotts executable.
EXECUTABLE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'install', 'melotts'))

melotts_args = []

# Load arguments from arguments.json if it exists
try:
    arguments_json_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'arguments.json'))
    if os.path.exists(arguments_json_path):
        with open(arguments_json_path, 'r') as f:
            args_config = json.load(f)
            # Map the arguments from the JSON file
            for key, value in args_config.items():
                melotts_args.append(f'--{key}')
                melotts_args.append(str(value))
        print(f'Loaded arguments from {arguments_json_path}')
    else:
        print(f'No arguments.json found at {arguments_json_path}, using default arguments')
except Exception as e:
    print(f'Error loading arguments.json: {e}')
# --- End Configuration ---

def sleep(seconds):
    """Sleep function that handles interruptions."""
    try:
        threading.Event().wait(seconds)
    except KeyboardInterrupt:
        pass

def start_melotts_process():
    """Starts and initializes the melotts C++ process."""
    global melotts_process

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    command = [EXECUTABLE_PATH] + melotts_args

    print(f"Starting melotts process: {' '.join(command)} from {project_root}")

    try:
        melotts_process = subprocess.Popen(
            command,
            cwd=project_root,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1, # Line-buffered
            encoding='utf-8',
            errors='ignore'
        )
    except FileNotFoundError:
        print(f"Error: Executable not found at {EXECUTABLE_PATH}")
        print("Please build the C++ project and ensure the 'melotts' executable is in the '../install/' directory.")
        return False

    # Ensure the process is terminated on script exit
    atexit.register(lambda: melotts_process.terminate())

    # Thread to continuously log stderr without blocking
    def log_stderr(pipe):
        for line in iter(pipe.readline, ''):
            print(f"[melotts-stderr]: {line.strip()}")

    threading.Thread(target=log_stderr, args=(melotts_process.stderr,), daemon=True).start()

    # Wait for the process to be ready by reading stdout until the first prompt appears
    print("Waiting for melotts process to initialize...")
    for line in iter(melotts_process.stdout.readline, ''):
        print(f"[melotts-stdout]: {line.strip()}")
        if "Enter a sentence" in line:
            print("Melotts process is ready to accept requests.")
            return True

    print("Melotts process exited before initialization was complete.")
    return False

def synthesis_worker():
    """
    A single worker thread that consumes tasks from the request_queue,
    processes them, and returns the result to the waiting request thread.
    """
    while True:
        job = request_queue.get()
        sentence = job['sentence']
        output_path = job['output_path']
        result_queue = job['result_queue']
        is_success = False

        print(f"Worker processing request: sentence='{sentence}'")

        if melotts_process is None or melotts_process.poll() is not None:
            print("Error: melotts process is not running. Cannot process request.")
            result_queue.put(False)
            request_queue.task_done()
            continue

        try:
            # The single worker thread model means we don't need a lock here,
            # as this is the only thread interacting with the process stdin/stdout.
            melotts_process.stdin.write(sentence + '\n')
            melotts_process.stdin.flush()

            for line in iter(melotts_process.stdout.readline, ''):
                print(f"[melotts-stdout]: {line.strip()}")
                if "Enter the output wav file path" in line:
                    break
                
            sleep(0.1)  # Small delay to ensure melotts is ready for the next input

            melotts_process.stdin.write(output_path + '\n\n')
            melotts_process.stdin.flush()

            output_seen = False
            prompt_seen = False
            for line in iter(melotts_process.stdout.readline, ''):
                stripped_line = line.strip()
                print(f"[melotts-stdout]: {stripped_line}")
                if "Saved audio to" in stripped_line:
                    output_seen = True
                if "[DEBUG] do_synthesize finished." in stripped_line:
                    print("Debug: Synthesis function finished.")
                if "[DEBUG] Top of interactive loop." in stripped_line:
                    print("Debug: C++ loop restarted.")
                if "Enter a sentence" in stripped_line:
                    prompt_seen = True
                    break  # The prompt is the last thing we expect for this transaction
            is_success = output_seen and prompt_seen

        except Exception as e:
            print(f"An error occurred in the worker while communicating with the melotts process: {e}")
            is_success = False
        
        # Send the result back to the waiting Flask request thread
        result_queue.put(is_success)
        request_queue.task_done()


@app.route('/synthesize', methods=['POST'])
def synthesize_endpoint():
    data = request.get_json()
    if not data or 'sentence' not in data or 'outputPath' not in data:
        return jsonify({'success': False, 'error': 'Invalid request. "sentence" and "outputPath" are required.'}), 400

    output_path = os.path.abspath(data['outputPath'])
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # A temporary queue to get the result back from the worker
    result_queue = queue.Queue(maxsize=1)

    # Create a job and put it on the main queue
    job = {
        'sentence': data['sentence'],
        'output_path': output_path,
        'result_queue': result_queue
    }
    request_queue.put(job)

    # Block and wait for the worker to process the job and return a result
    print("Request thread waiting for synthesis to complete...")
    is_success = result_queue.get()
    print(f"Request thread received result: {is_success}")

    if is_success:
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'Synthesis failed. Check server logs for details.'}), 500

if __name__ == '__main__':
    if start_melotts_process():
        # Start the single worker thread that will process the queue
        threading.Thread(target=synthesis_worker, daemon=True).start()
        
        print("Starting Flask server on http://0.0.0.0:8802")
        app.run(host='0.0.0.0', port=8802)
    else:
        print("Failed to start the melotts C++ process. The server will not run.")
