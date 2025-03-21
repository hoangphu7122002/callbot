#!/bin/bash

# Đường dẫn thực đến thư mục của bạn
WORKING_DIR="/home/hoangphu7122002/callbot"
PYTHON_FILE="fs_test9.py"

# Chuyển đến thư mục dự án
cd "$WORKING_DIR" || exit

# Kích hoạt môi trường ảo
source myenv/bin/activate

# Chạy Python script liên tục
#while true; do
echo "Running Python script..."
python3 "$WORKING_DIR/$PYTHON_FILE"
done
