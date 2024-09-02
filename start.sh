#!/bin/bash

# Обновляем pip
python3 -m pip install --upgrade pip

# Устанавливаем зависимости из файла req.txt
pip3 install -r req.txt

# Запускаем telegram.py в фоне
python3 telegram.py

