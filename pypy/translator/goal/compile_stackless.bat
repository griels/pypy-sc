python -c "import time; print time.ctime(), 'compile start'" >> compile.log
translate.py --batch --stackless
python -c "import time; print time.ctime(), 'compile stop'" >> compile.log
