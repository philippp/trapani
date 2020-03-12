#!/usr/bin/env bash
if [ 1 ]
then
		if [ -z "`ps aux | grep web_service.py | grep -v grep`" ]
		then
				screen -d -m python3 ./web_service.py
		fi
		sleep 10
fi
