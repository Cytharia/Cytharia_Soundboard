#!/bin/env python3

from evdev import InputDevice, categorize, ecodes
from time import sleep
import datetime
import pygame
import os
import random
import re
import numpy as np
import pulsectl
import threading
from pathlib import Path

# Global counts to ensure we don't immediately repeat the same file
lastRand = [[-1, -1, -1, -1, -1, -1],
	[-1, -1, -1, -1, -1, -1],
	[-1, -1, -1, -1, -1, -1],
	[-1, -1, -1, -1, -1, -1],
	[-1, -1, -1, -1, -1, -1],
	[-1, -1, -1, -1, -1, -1]]
	
# Base path for where all our sounds are stored
basePath = '<BASE DIRECTORY>'

# Wait until devices are connected before continuing
def waitForDevices():
	while True:
		print('Waiting for devices...')
		inputList = os.listdir('/dev/input/')
		
		outputListCont = []
		speakerList = []
		for folder in inputList:
			if re.search("event",folder):
				controller = InputDevice('/dev/input/' + folder)
				print('   ' + controller.name + ' in ' + folder)
				if controller.name == "PRC-1 Consumer Control":
					outputListCont.append(folder)
				if controller.name == "EWA Audio A106Pro (AVRCP)":
					speakerList.append(folder)
				#if controller.name == "EWA Audio A109mini (AVRCP)":
				#	speakerList.append(folder)
		if not outputListCont or not speakerList:
			print('Waiting for speaker and controller...')
		else:
			controller = InputDevice('/dev/input/' + outputListCont[1])
			print('Found ' + controller.name + ' as main controller on input ' + outputListCont[1] + '.\n')
			return controller
		sleep(1)

# Set volume for the audio device
def setVolume(pulse,level):
	deviceName = 'EWA Audio A106Pro'
	for sink in pulse.sink_list():
		if sink.description == deviceName:
			break
	pulse.volume_set_all_chans(sink,level)

# Link in current Ad Hoc selection
def linkAdHoc(button,counter):
	specialDir = os.listdir(basePath + 'sorted/special/')
	os.unlink(basePath + 'lp' + str(button))
	os.symlink(basePath + 'sorted/special/' + specialDir[counter], basePath + 'lp' + str(button))

# Long press functionality
def longPress(button):
	return getRandomFile(basePath + 'lp' + str(button),-1,-1)

def getSpecialFile(x,y):
	filename = getRandomFile(basePath + 'pos' + str(x) + str(y) + '_special',x,y)
	return filename	

def getRandomFile(folder,x,y):
	filelist = os.listdir(folder)
	numFiles = len(filelist)
	#print('   Found ' + str(numFiles) + ' files!\n')
	
	if x == -1 or y == -1:
		randSound = random.randint(0,numFiles-1)
		return os.path.join(folder, filelist[randSound])
	elif numFiles > 0:
		while True:
			randSound = random.randint(0,numFiles-1)
			if randSound != lastRand[x][y]:
				break
			if numFiles == 1:
				break
			print('Chose the same sound, rolling again!')
		lastRand[x][y] = randSound
		return os.path.join(folder, filelist[randSound])
	# If no files in the directory, just load up the silence file
	else:
		return basePath + 'pos00/silence.mp3'

def getSound(x,y):		# Button 2 increments x, Button 3 increments y
	filename = getRandomFile(basePath + 'pos' + str(x) + str(y),x,y)
	return filename
	
# Setup the environment by initializing pygame, finding the right controller,
# setting up initial variables, and configuring button actions

pygame.mixer.pre_init(44100, -16, 2, 128)
pygame.init()
print('Done loading pygame!')
controller = waitForDevices()

x = 0			# Current sound, initialize slot to 0/0
y = 0
lastX = 0		# Initialize last sound played
lastY = 0
lastSpecial = 0

# Start with webActive so we can toggle it with a command
webActive = 1

# Special sound file counts and thresholds for playing a sound every X activations
specialCount = [[0, 0, 0, 0, 0, 0],
	[0, 0, 0, 0, 0, 0],
	[0, 0, 0, 0, 0, 0],
	[0, 0, 0, 0, 0, 0],
	[0, 0, 0, 0, 0, 0],
	[0, 0, 0, 0, 0, 0]]
specialThresh = [[-1, 6, -1, -1, -1, -1],
	[-1, -1, -1, -1, -1, -1],
	[2, -1, -1, -1, -1, -1],
	[-1, -1, -1, -1, -1, -1],
	[-1, -1, -1, -1, -1, -1],
	[-1, -1, -1, -1, -1, -1]]
	
playingFile = 0		# Indicates whether a sound has been started

print('Using ' + controller.name + ' as main controller.\n')

# Configurable buttons, set for PRC-1 Consumer Control device
button1 = 164
button2 = 114
button3 = 115
button4 = 163
button5 = 165
button6 = 116

# Minimum time for long press reaction
longPressTime = 0.5
longerPressTime = 3
modifierHoldTime = 0.1
button2_held = 0
button3_held = 0

# Initialize the queued sound to silence
nextfile = getSound(0,0)
sound = pygame.mixer.Sound(nextfile)

# Set master volume
os.system("amixer -D pulse sset Master 100%")

# Flag for ad hoc mode
adHoc = 0

# Set up queue for the web app and spawn a thread
webThread = threading.Thread(target=webSound)
webThread.start()

# Default volume for the sounds is 50%
currentVolume = .5
sound.set_volume(currentVolume)
adjustIncrement = 0.1
pulse = pulsectl.Pulse('volume-control')

# Play boot sound
soundFile = basePath + 'boot_sound'
sound = pygame.mixer.Sound(soundFile)
sound.set_volume(1)
setVolume(pulse,currentVolume)
sound.play()
sound.set_volume(1)

# Infinite input loop for reading inputs from the controller
for event in controller.read_loop():
	if event.type == ecodes.EV_KEY:
		if adHoc == 0:
			pressTime = event.sec + event.usec / 1000000
		
			# Compensate for volume buttons when they're held down
			if button2_held == 1 or button3_held == 1:
				setVolume(pulse,currentVolume)
		
			# Record the press time for buttons so we can measure when we have a long press on release
			if event.value == 1:
				# Long press detection
				if event.code == button1:
					button1_pressTime = pressTime
				if event.code == button2:
					button2_pressTime = pressTime
					button2_held = 1
				if event.code == button3:
					button3_pressTime = pressTime
					button3_held = 1
		
			if event.value == 0:
				# Button 1 release
				if event.code == button1:
					if button1_pressTime + longPressTime < pressTime:
						# If last sound was not a long press
						x = lastX
						y = lastY
						if (lastX >= 0):
							if lastSpecial == 0:
								soundFile = getSound(x,y)
							else:
								soundFile = getSpecialFile(x,y)
							sound = pygame.mixer.Sound(soundFile)
						# If last sound was a long press
						else:
							soundFile = longPress(abs(x))
							sound = pygame.mixer.Sound(soundFile)
					pygame.mixer.stop()
					
					setVolume(pulse,currentVolume)
					sound.play()
					playingFile = 1
					print('Playing %s ...' % soundFile)
					tempCount = specialCount[x][y] + 1
					specialCount = [[0, 0, 0, 0, 0, 0],
						[0, 0, 0, 0, 0, 0],
						[0, 0, 0, 0, 0, 0],
						[0, 0, 0, 0, 0, 0],
						[0, 0, 0, 0, 0, 0],
						[0, 0, 0, 0, 0, 0]]
					specialCount[x][y] = tempCount
					if x > 0 or y > 0:
						lastX = x	# Preserve the last sound played for long press
						lastY = y
					if x < 0:
						lastX = x
						lastY = 0
					x = 0
					y = 0
					soundFile = getSound(0,0)
					setVolume(pulse,currentVolume)
					sound.set_volume(1)
					sound = pygame.mixer.Sound(soundFile)
					
				# Button 2 release
				if event.code == button2:
					button2_held = 0
					timeTest = pressTime - button2_pressTime
					if button2_pressTime + longerPressTime < pressTime:
						adHoc = 1
						ahButton = 2
						ahCounter = 0
						print('Entering Ad Hoc Mode...')
						continue
					elif button2_pressTime + longPressTime < pressTime:
						soundFile = longPress(2)
						x = -2
					else:
						if (x < 0):
							x = 0
						x = x + 1
						if x == 6:
							x = 0
						if specialCount[x][y] >= specialThresh[x][y] and specialThresh[x][y] > -1:
							specialCount[x][y] = 0
							soundFile = getSpecialFile(x,y)
							lastSpecial = 1
						else:
							soundFile = getSound(x,y) 
							lastSpecial = 0
					sound = pygame.mixer.Sound(soundFile)
					print('Loaded sound ' + soundFile)
				# Button 3 release
				if event.code == button3:
					button3_held = 0
					timeTest = pressTime - button3_pressTime
					if button3_pressTime + longerPressTime < pressTime:
						adHoc = 1
						ahButton = 3
						ahCounter = 0
						print('Entering Ad Hoc Mode...')
						continue
					elif button3_pressTime + longPressTime < pressTime:
						soundFile = longPress(3)
						x = -3
					else:
						if (x < 0):
							x = 0
						y = y + 1
						if y == 6:
							y = 0
						if specialCount[x][y] >= specialThresh[x][y] and specialThresh[x][y] > -1:
							specialCount[x][y] = 0
							soundFile = getSpecialFile(x,y)
							lastSpecial = 1
						else:
							soundFile = getSound(x,y)
							lastSpecial = 0
					sound = pygame.mixer.Sound(soundFile)
					print('Loaded sound ' + soundFile)					
				# Button 4 release
				if event.code == button4:
					print('Increasing volume...')
					currentVolume += adjustIncrement
					if currentVolume > 1:
						currentVolume = 1
					else:
						soundFile = getSound(0,0)
						sound = pygame.mixer.Sound(soundFile)
						setVolume(pulse,currentVolume)
						#sound.play()
						print('Volume adjusted to ' + str(int(currentVolume*100)) + '%\n')
					
				# Button 5 release
				if event.code == button5:
					print('Decreasing volume...')
					currentVolume -= adjustIncrement
					if currentVolume < 0:
						currentVolume = 0
					else:
						soundFile = getSound(0,0)
						sound = pygame.mixer.Sound(soundFile)
						setVolume(pulse,currentVolume)
						#sound.play()
						print('Volume adjusted to ' + str(int(currentVolume*100)) + '%\n')

		# Ad Hoc mode, allows user to load up long-press button 2 and 3 on the fly
		if adHoc == 1:
			if event.value == 0:
				# Determine the number of sounds in the special folder
				specialDir = os.listdir(basePath + '/sorted/special/')
				specialDir.sort()
				maxSpecial = len(specialDir) - 1
			
				# Button 1 leaves Ad Hoc mode
				if event.code == button1:
					x = 0
					y = 0
					soundFile = getSound(0,0)
					sound = pygame.mixer.Sound(soundFile)
					adHoc = 0
					print('Entering sound mode...')
				
				# Button 2 cycles to the next file
				if event.code == button2:
					ahCounter = ahCounter + 1
					if ahCounter > maxSpecial:
						ahCounter = 0
					
				# Button 3 cycles to last file
				if event.code == button3:
					ahCounter = ahCounter - 1
					if ahCounter < 0:
						ahCounter = maxSpecial

				# Button 2 and Button 3 both link in and play new sound
				if event.code == button2 or event.code == button3:
					linkAdHoc(ahButton,ahCounter)
					pygame.mixer.stop()
					soundFile = getRandomFile(basePath + 'lp' + str(ahButton),0,0)
					setVolume(pulse,currentVolume)
					sound = pygame.mixer.Sound(soundFile)
					sound.set_volume(1)
					sound.play()
