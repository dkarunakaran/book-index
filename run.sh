#!/bin/bash

# Run below step one by one in terminal

docker build -t book_index_image .
docker run --gpus all --net=host -it -v /home/beastan/Documents/projects/book-index/data:/app/data book_index_image

