#!/usr/bin/env bash
if [ 1 ]
then
		if [ -z "`ps aux | grep dispatcher_service.py | grep -v grep`" ]
		then
				python3 ./dispatcher_service.py continuous_dispatch
		fi
		sleep 10
fi
