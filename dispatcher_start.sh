#!/usr/bin/env bash
if [ 1 ]
then
		if [ -z "`ps aux | grep dispatcher_service.py | grep -v grep`" ]
		then
				screen -d -m python3 ./dispatcher_service.py continuous_dispatch
		fi
fi
