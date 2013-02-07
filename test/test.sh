#!/bin/sh


CURRDIR=`pwd`
cd ..
./processor.py $CURRDIR/unittest.cfg $CURRDIR/unittest.json 
for file in `ls unit*.csv`
do 
	echo Comparing $file to test_$file
	diff test/test_results/test_$file $file
done
rm -fr unit*.csv
cd $CURRDIR
