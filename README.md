# melotts.axcl

This repository is a fork of [melotts.axcl](https://github.com/ml-inory/melotts.axcl), which is an implementation of the [MeloTTS](https://arxiv.org/abs/2211.13227) text-to-speech model runing on LLM8850 accelerator card.

In order to provide continus audio synthesis service, we have added a server implementation in Python that interacts with the melotts C++ binary. The server listens for incoming text requests, processes them using the melotts model, and returns the generated audio files. In this way, the program does have to load the model for each request, significantly improving performance for multiple requests.

## Compile on Pi 5

aarch64 build script:

```
sudo chmod +x build_aarch64.sh
./build_aarch64.sh
```

## Download Models

[Chinese Models](https://huggingface.co/M5Stack/MeloTTS-Chinese-ax650)

[English Models](https://huggingface.co/M5Stack/MeloTTS-English-ax650)

[Japanese Models](https://huggingface.co/M5Stack/MeloTTS-Japanese-ax650)

[Spanish Models](https://huggingface.co/M5Stack/MeloTTS-Spanish-ax650)

You can fork the model repositories and link them in `arguments.json` for easier management.

## Start Server

Run in the root directory of the `bash serve.sh`, which will start the server at `http://localhost:8802`.

## Arguments Configuration

The server uses the `arguments.json` file to configure the model paths and parameters. Make sure to update the paths in `arguments.json` to point to the correct model files you downloaded.

For example, for English models, the `arguments.json` should look like this:

```json
{
  "encoder": "/home/pi/MeloTTS-English-ax650/encoder-en.onnx",
  "decoder": "/home/pi/MeloTTS-English-ax650/decoder-en-br.axmodel",
  "lexicon": "/home/pi/MeloTTS-English-ax650/lexicon-en.txt",
  "token": "/home/pi/MeloTTS-English-ax650/tokens-en.txt",
  "g": "/home/pi/MeloTTS-English-ax650/g-en-br.bin",
  "volume": "4"
}
```

## Request Format

The server accepts POST requests with a JSON payload containing the text to be synthesized. The request format is as follows:

```bash
curl -X POST http://localhost:8802/synthesize \
     -H "Content-Type: application/json" \
     -d '{"sentence": "hello, i'm a student from some where", "outputPath": "/path/to/output.wav"}'
```

Response:
```json
{
  "success": true,
}
```

Error Response:
```json
{
  "success": false,
  "error": "Error message here"
}
```

If the melotts process is not running correctly, use `/restart` endpoint to restart it:

```bash
curl -X POST http://localhost:8802/restart
```

## Run as Systemd Service

A systemd service file `melotts.service` is provided to run the server as a background.

To enable and start the service, use the following commands:

```bash
sudo bash startup.sh
```
