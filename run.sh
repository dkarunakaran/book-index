#!/bin/bash

# Run below step one by one in terminal

docker build -t extract_text_image .
docker run --gpus all --net=host -it -v /home/beastan/Documents/projects/text-extract-image/data:/app/data extract_text_image

