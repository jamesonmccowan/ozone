find *.png > frames.txt
mencoder -nosound -ovc lavc -lavcopts vcodec=mpeg4:mbd=2:trell -o timelapse.avi -mf type=png:fps=20 mf://@frames.txt
rm frames.txt
