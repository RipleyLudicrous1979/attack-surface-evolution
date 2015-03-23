import json
import os
import shutil
import sys
from django.conf import settings

import requests
import slacker

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "FFMpegEvolution.settings")

from app.analysis import r
from app.management.commands import initdb
from app.models import Revision

slack_token = None

def setup():
	global slack_token

	# Create workspace and repository directories
	if not os.path.exists(settings.NIGHTLY_OUT_DIR):
		os.makedirs(settings.NIGHTLY_OUT_DIR, mode=0o777)
	
	# Read Slack API token from the local store
	api_token_file = os.path.join(os.path.expanduser('~'),
		settings.SLACK_API_TOKEN_FILE)

	if os.path.exists(api_token_file):
		with open(api_token_file, 'r') as _file:
			slack_token = _file.read().strip('\n')

def teardown():
	# Remove workspace directory
	shutil.rmtree(settings.WORKSPACE_DIR)

def is_cve_updated():
	response = requests.get(settings.FFMPEG_SECURITY_SRC_URL)
	if response.json()['sha'] != settings.FFMPEG_SECURITY_FILE_SHA:
		return True
	return False

def slackpost(status):
	global slack_token

	if slack_token:
		slack = slacker.Slacker(slack_token)

		message = {
			'channel': settings.SLACK_CHANNEL['name'],
			'username': settings.SLACK_USERNAME,
			'text': '',
		}
		
		cve_sync_status = 'In-sync'
		if is_cve_updated():
			cve_sync_status = 'Out-of-sync'
			status = 1

		# POST to Slack
		if status == 0 or status == 1:
			# Success or Warning
			response = slack.files.upload(settings.OUTPUT_FILE, 
				title='Association Results',
				filename='results.txt',
				channels=[settings.SLACK_CHANNEL['id']])

			color = 'good'

			if status == 1:
				color = 'warning'
			
			fields = list()
			fields.append({'title': 'Outcome',
				'value': 'Success', 'short': True})
			fields.append({'title': 'CVE Sync. Status',
				'value': cve_sync_status, 'short': True})

			message['attachments'] = json.dumps([{
				'fallback': 'Attack Surface Nightly Run',
				'title': 'Attack Surface Nightly Run',
				'color': color,
				'fields': fields
			}])

			slack.chat.post_message(**message)
		elif status == 2:
			# Error
			pass
	else:
		print('Slack API token was not appropirately initialized')

def main():
	global slack_token

	# Setup the nightly run
	setup()

	# Load data for all branches except 0.5.0
	revisions = Revision.objects.filter(type='b').exclude(number='0.5.0')

	# TODO: Call initdb, loaddb for each revision

	# Run R analysis
	status = r.run()

	slackpost(status)

	# Teardown the nightly run
	teardown()

if __name__ == '__main__':
	main()