# -*- coding: utf-8 -*-

import sys
import os
import json
import re
import time
import logging
import logging.handlers
import traceback
import telepot
import smtplib
import random
from datetime import datetime
from collections import OrderedDict
from config import settings
from pprint import pprint
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from textblob import TextBlob
from telepot.loop import MessageLoop
from textblob.classifiers import NaiveBayesClassifier



class BookingAgent(object):

	def __init__(self, training_data, smtp_email, smtp_pass, smtp_server, smtp_port, telegram_bot_token):
		self.counter = 0
		self.bot_pos_count=0
		self.bot_neg_count=0
		self.update = False
		self.cancel_order = False
		self.user_greet  = False
		self.intent_satisfied = False
		self.str_time = int(datetime.fromtimestamp(int(time.time()),tz=None).strftime("%H"))
		self.unix_time = int(time.time())
		self.book_table = ''
		self.book_table_type = ''
		self.user_phone = ''
		self.user_email = ''
		self.booking_time = ''
		self.temp_holder = ''
		self.training_data = training_data
		self.smtp_email = smtp_email
		self.smtp_pass = smtp_pass
		self.smtp_server = smtp_server
		self.smtp_port = smtp_port
		self.hotel_name = settings['agent']['hotel_name']
		self.table_type = ['bachelor', 'couple', 'family']
		self.emoji_table_type = ['💃🕺 bachelor', '👫 couple', '👪 family']
		self.max_guest_range = [str(max_guest_range) for max_guest_range in range(1,21)]
		self.bot_greet_keywords = ['hey','hello','/start','hi', 'howdy', 'hows is it going?','yes','no','continue', 'book a table','hi book a table','i want to book a table','book a table','nice to see you','how are you?']
		self.bot_pos_keywords = ['ok','sure','alrite','yes']
		self.bot_neg_keywords = ['sorry, I did not understand that.','what was that ?','sorry, I did not catch that','i’m afraid it is not clear what you mean to say']
		self.LOG_FILENAME = '%s'%('BotLog.log')
		self.log = logging.getLogger(__name__)
		self.log.setLevel(logging.DEBUG)
		self.formatter = logging.Formatter(fmt='%(asctime)s | Line No : %(lineno)d | Level : %(levelname)s | File : %(filename)s | Caller : %(funcName)s | Message : %(message)s')
		self.handler = logging.handlers.RotatingFileHandler(self.LOG_FILENAME, maxBytes=10**6, backupCount=5)
		self.handler.setFormatter(self.formatter)
		self.log.addHandler(self.handler)
		with open(self.training_data, 'r') as training_data:
			self.trainer = NaiveBayesClassifier(training_data, format='json')
		self.telegram_bot = telepot.Bot(telegram_bot_token)
		# GET BOT ID AND DETAILS
		# print self.telegram_bot.getMe()


	#---------------------------------------
	# Function = get_unixstamp_from_str
	# Convert From String To Unixstamp Time
	# @param = val(string)
	# @return = timestamp(int)
	#---------------------------------------
	def get_unixstamp_from_str(self,val):
		try:
			dt = datetime.strptime(str(val),"%H:%M")
		except:
			dt = datetime.strptime(str(val),"%H.%M")
		dt_now = datetime.now()
		dt = dt.replace(year=dt_now.year, month=dt_now.month, day=dt_now.day)
		return int(time.mktime(dt.utctimetuple()))

	
	#---------------------------------------
	# Function = telegram_handler
	# Telepot Handler For Telegram
	# @param = msg(json-encoded)
	# @return = None
	#---------------------------------------
	def telegram_handler(self,msg):
			try:
				# -------------------------
				# GET USER DETAILS BLOCK
				# -------------------------
				self.log.info("Agent Started")
				user = self.telegram_bot.getUpdates()
				user_name = user[0]['message']['from']['first_name']
				user_id = user[0]['message']['from']['id']
				user_type = user[0]['message']['from']['is_bot']
				user_lang = user[0]['message']['from']['language_code']
				user_timestamp = user[0]['message']['date']

				# ---------------------------------------------
				# EXTRACT HEADER INFO FROM USER TELEGRAM MSG
				# ---------------------------------------------
				content_type, chat_type, chat_id = telepot.glance(msg)
				# DEBUG HEADER MSG 
				# print msg

				# ---------------------------------------------------------------------------------------------------------------------------------
				# INTENT HANDLER TO GET 'SENTIMENTS' AND 'INTENT TYPES' BLOCK
				# THIS BLOCK REQUIRES 'DATASET' TO TRAIN IN ORDER TO GIVE POSITIVE RESULT USING 'NLP'
				# TRAINING WITH MORE DATASET WILL MAKE BOT RECOGNISE INTENT TYPE AND SENTIMENTS MORE EFFECTIVELY,
				# WHICH WILL HELP THE BOT TO CREATE MORE MEANINGFUL CONVERSATIONS
				# ---------------------------------------------------------------------------------------------------------------------------------
				intent_handler = json.loads(self.intent_handler(msg))

				# -----------------------------------
				# RECOGNISE EMAIL,PHONE,TIME BLOCK
				# -----------------------------------
				get_booking_time = re.match('[\d]{2}:[\d]{2}',intent_handler['agent_response']['msg_text']) or re.match('[\d]{2}\.[\d]{2}',intent_handler['agent_response']['msg_text'])
				get_phone = re.match('[\d]{10}',intent_handler['agent_response']['msg_text'])
				get_email = re.match(r"([\w.-]+)@([\w.-]+)", intent_handler['agent_response']['msg_text'])

				# --------------------------------------------
				# ONLY TEXT IS VALID FOR PROCESSING FROM USER
				# --------------------------------------------
				if content_type == 'text' and intent_handler['agent_response']['msg_text'] in self.bot_greet_keywords or intent_handler['agent_response']['msg_text'] in self.table_type or intent_handler['agent_response']['msg_text'] in self.max_guest_range or get_booking_time>0 or get_email>0 or get_phone>0:
					
					# -----------------------------------
					# END CHAT BLOCK
					# -----------------------------------
					if self.intent_satisfied==True and self.counter<2 and self.cancel_order == False and intent_handler['agent_response']['msg_text'] != 'cancel':
						self.telegram_bot.sendMessage(chat_id,"\n\rIt Looks Like You Have Already Set The Boat Sailing, Sit Back And Relax Will Take It From Here ! BYE BYE :)\n\r\n\r")
						self.counter+=1

					# -----------------------------------------------------------
					# NORMAL GREETINGS AND WISH USER AS PER CURRENT TIME BLOCK
					# -----------------------------------------------------------
					if self.str_time>=00 and self.str_time<12:
						greet = "Good Morning !"
					elif self.str_time>=12 and self.str_time<15:
						greet = "Good Afternoon !"
					elif self.str_time>=15 and self.str_time<=23:
						greet = "Good Evening"
					if self.user_greet == False:
						self.telegram_bot.sendMessage(chat_id,'😃'.format(user_name))
						self.telegram_bot.sendMessage(chat_id,greet)
						self.telegram_bot.sendMessage(chat_id,"🙏 Greetings From {} 🙋🏰!".format(self.hotel_name))
						self.telegram_bot.sendMessage(chat_id,"Hello {} 😃!".format(user_name))
						self.user_greet = True
	
					# -----------------------------------
					# UPDATE KEY BLOCK
					# -----------------------------------					
					if self.update==True and intent_handler['agent_response']['msg_text'] == 'yes':
						self.update=True
						self.telegram_bot.sendMessage(chat_id,"Okay !")
					elif self.update==True and intent_handler['agent_response']['msg_text'] == 'no':
						self.update=False
						self.temp_holder=''
						self.telegram_bot.sendMessage(chat_id,"Okay !")

					# -----------------------------------
					# TABLE TYPE SET CHECK AND UPDATE BLOCK
					# -----------------------------------
					if intent_handler['agent_response']['msg_text'] in self.table_type and self.book_table_type!='':
						self.telegram_bot.sendMessage(chat_id,"Table Type Already Added By You, Do You Want Me To Update : '%s' => '%s'"%(self.book_table_type,intent_handler['agent_response']['msg_text']))
						self.update = True
						self.temp_holder = intent_handler['agent_response']['msg_text']
					elif intent_handler['agent_response']['msg_text']=='yes' and  self.temp_holder in self.table_type and self.book_table_type!='' and self.update==True:
						self.book_table_type = self.temp_holder
						self.telegram_bot.sendMessage(chat_id,"Updated Your Preference")
						self.update = False
						self.temp_holder = ''
					elif intent_handler['agent_response']['msg_text'] in self.table_type:
						self.book_table_type = intent_handler['agent_response']['msg_text']
					
					# -----------------------------------
					# GUEST-RANGE SET CHECK AND UPDATE BLOCK
					# -----------------------------------
					if intent_handler['agent_response']['msg_text'] in self.max_guest_range and self.book_table!='':
						self.telegram_bot.sendMessage(chat_id,"No Of Seats Required Already Added By You, Do You Want Me To Update : '%s' => '%s'"%(self.book_table,intent_handler['agent_response']['msg_text']))
						self.update = True
						self.temp_holder = intent_handler['agent_response']['msg_text']
					elif intent_handler['agent_response']['msg_text']=='yes' and  self.temp_holder in self.max_guest_range and self.book_table!='' and self.update==True:
						self.book_table = self.temp_holder
						self.telegram_bot.sendMessage(chat_id,"Updated Your Preference")
						self.update = False
						self.temp_holder = ''
					elif intent_handler['agent_response']['msg_text'] in self.max_guest_range:
						self.book_table = intent_handler['agent_response']['msg_text']
										
					# -----------------------------------
					# PHONENUMBER SET CHECK AND UPDATE BLOCK
					# -----------------------------------
					if get_phone and len(intent_handler['agent_response']['msg_text'])==10 and self.user_phone!='':
						self.telegram_bot.sendMessage(chat_id,"Phonenumber Already Provided, Do You Want Me To Update : '%s' => '%s'"%(self.user_phone,intent_handler['agent_response']['msg_text']))
						self.update = True
						self.temp_holder = intent_handler['agent_response']['msg_text']
					elif intent_handler['agent_response']['msg_text']=='yes' and len(self.temp_holder)==10 and self.user_phone!='' and self.update==True:
						self.user_phone = self.temp_holder
						self.telegram_bot.sendMessage(chat_id,"Updated Your Preference")
						self.update = False
						self.temp_holder = ''
					elif get_phone and len(intent_handler['agent_response']['msg_text'])==10:
						self.user_phone = intent_handler['agent_response']['msg_text']
						
					# ------------------------------------------------------------------------------------------------------
					# BOOKING TIME FOR CURRENT DAY, TIME SHOULD BE 1 HOUR AHEAD AND NOT PAST SET CHECK AND UPDATE BLOCK
					# ------------------------------------------------------------------------------------------------------
					if get_booking_time and self.booking_time!='':
						self.telegram_bot.sendMessage(chat_id,"Booking Time Already Provided, Do You Want Me To Update : '%s' => '%s'"%(self.booking_time,intent_handler['agent_response']['msg_text']))
						self.update = True
						self.temp_holder = intent_handler['agent_response']['msg_text']
					elif intent_handler['agent_response']['msg_text']=='yes' and self.booking_time!='' and self.update==True:
						if len(self.temp_holder)<=5:
							self.booking_time = self.temp_holder
							self.telegram_bot.sendMessage(chat_id,"Updated Your Preference")
							self.update = False
							self.temp_holder = ''
					elif get_booking_time:
						self.booking_time = intent_handler['agent_response']['msg_text']

					# -----------------------------------
					# MAIL SET CHECK AND UPDATE BLOCK
					# -----------------------------------
					if get_email and self.user_email!='':
						self.telegram_bot.sendMessage(chat_id,"Email Already Provided, Do You Want Me To Update : '%s' => '%s'"%(self.user_email,intent_handler['agent_response']['msg_text']))
						self.update = True
						self.temp_holder = intent_handler['agent_response']['msg_text']
					elif intent_handler['agent_response']['msg_text']=='yes' and self.user_email!='' and self.update==True:
						self.user_email = self.temp_holder
						self.telegram_bot.sendMessage(chat_id,"Updated Your Preference")
						self.update = False
						self.temp_holder = ''
					elif get_email:
						self.user_email = get_email.group()
					
					# -------------------------
					# MESSAGES TO USER BLOCK
					# -------------------------
					if self.book_table_type =='' and self.update==False:
						self.telegram_bot.sendMessage(chat_id,"🙄🤔 Please Select Table Type In Order To Start Your Booking !")
						self.telegram_bot.sendMessage(chat_id,"Please Select Table Type 🍽👈 Choices :")
						for table_type in self.emoji_table_type:
							self.telegram_bot.sendMessage(chat_id,"=> "+table_type.title())
						
					elif self.book_table =='' or len(intent_handler)>2 and self.update==False:
						self.telegram_bot.sendMessage(chat_id,"✔👈 Please Select Total No Of Seats Required ( Maximum Limit Per Customer : 20 Per Table)" )
					
					elif self.booking_time !='' and self.get_unixstamp_from_str(self.booking_time)<=int(time.time()) :
						self.booking_time = ''
						self.telegram_bot.sendMessage(chat_id,"🕙📢✖ Booking Time Cannot Be Current Time Or Time In Past, Please Try Again !")

					elif self.booking_time =='' and self.update==False:
						self.telegram_bot.sendMessage(chat_id,"🕙📢🙄🤔 Please Select Your Booking Time (IST 24.Hr)" )
						self.telegram_bot.sendMessage(chat_id,"🕙 Hotel Working Hours : 24x7")
						self.telegram_bot.sendMessage(chat_id,"✔ Valid Format Example : 15.00 Or 15:00")

					elif self.user_phone =='' and self.update==False:
						self.telegram_bot.sendMessage(chat_id,"✔📱 Please Provide Us Your 10 Digit Mobile Number To Proceed Ahead")
					
					elif self.user_email =='' and self.update==False:
						self.telegram_bot.sendMessage(chat_id,"✔📧 Please Provide Us Your Mail Id To Proceed Ahead")
					
					elif self.book_table>0 and self.book_table_type>0 and self.user_phone>0 and self.user_email>0 and self.counter<1 and self.update==False:
						self.intent_satisfied = True
						data = "******************************\n\r👑 Name : {}\n\r📱 Phone : {}\n\r📧 Email : {}\n\r🍽 Booking Table Type : {}\n\r👍 Seating Capacity : {}\n\r🕙 Booking Time (IST 24.Hr) : {}\n\r******************************".format(user_name.title(),self.user_phone,self.user_email,self.book_table_type.title(),self.book_table,self.booking_time)
						self.telegram_bot.sendMessage(chat_id,"😎 🎈🎊🎉 Booking Confirmed, Please SET CHECK Your Mail ! 🎈🎊🎉")
						self.telegram_bot.sendMessage(chat_id,"(SET CHECK Your Spam/Junk Folder If Mail Not Found In Inbox)")
						self.telegram_bot.sendMessage(chat_id,"||||||||||||||||||||||||||||||||||||||\r\n\r\n")
						self.telegram_bot.sendMessage(chat_id,"📅 Summary Of Booking 📅")
						self.telegram_bot.sendMessage(chat_id,data)
						self.telegram_bot.sendMessage(chat_id,"🙏😁 Thank You Looking Forward To Having You With Us 😃")
						self.telegram_bot.sendMessage(chat_id,"💬 Please Note : We Reserve The Right To Cancel The Booking Request If A 'No Show' Is Found After 50 Minutes Of Your Scheduled Time !")
						# Send Mail
						self.send_mail(self.user_email,data.replace('\n\r','<br>'))
						self.counter+=1


				elif intent_handler['agent_response']['msg_text']=='cancel' and self.cancel_order == False:
					self.book_table_type = ''
					self.book_table = ''
					self.booking_time = ''
					self.user_phone = ''
					self.user_email = ''
					self.cancel_order = False
					self.intent_satisfied = False
					self.temp_holder = ''
					self.update = False
					self.counter = 0
					self.telegram_bot.sendMessage(chat_id,"Ok %s Your Booking Has Been Cancelled, Thank You !"%(user_name))
					self.telegram_bot.sendMessage(chat_id,"To Continue Again With Your Booking => Type : 'Continue'")

				elif intent_handler['agent_response']['msg_text'] == 'help':
					self.telegram_bot.sendMessage(chat_id,"--- Help Guide ---")
					self.telegram_bot.sendMessage(chat_id,"---Steps To Book Your Table ---")
					self.telegram_bot.sendMessage(chat_id,"Initiate A Meaningful Conversation With Bot => 'Hi or Book A Table' Anything Humanly :)")
					self.telegram_bot.sendMessage(chat_id,"--------")
					self.telegram_bot.sendMessage(chat_id,"1. Select Table Type > Simple,Family,Couple")
					self.telegram_bot.sendMessage(chat_id,"2. Select No Of Seats > Min 1 - Max 20")
					self.telegram_bot.sendMessage(chat_id,"3. Select Your Booking Time (Future Value Only)")
					self.telegram_bot.sendMessage(chat_id,"4. Provide Us With Your Mobile Number")
					self.telegram_bot.sendMessage(chat_id,"5. Provide Us With Your Email")
					self.telegram_bot.sendMessage(chat_id,"6. Receive Confirmation In Message As Well As Email")
					self.telegram_bot.sendMessage(chat_id,"7. Your Table Is Booked :)")
					self.telegram_bot.sendMessage(chat_id,"8. To Cancel Your Booking Order Type =>'cancel'")
					self.telegram_bot.sendMessage(chat_id,"9. To Update The Field Simply Type The Option Again System Will Recognise It And Will Give You Prompt On Same")
					self.telegram_bot.sendMessage(chat_id,"\n\nTo Proceed Ahead With Your Booking => Type : 'Continue'")
				
				elif self.bot_neg_count>0:
					self.telegram_bot.sendMessage(chat_id,"Hey {} 😃!".format(user_name))
					self.telegram_bot.sendMessage(chat_id,"Type Help To Let Me Guide You")
					self.bot_neg_count-=1

				elif content_type == 'text' and intent_handler['agent_response']['msg_text']!='cancel' and intent_handler['agent_response']['msg_text']!='help' or get_booking_time>0==False or get_email>0==False or get_phone>0==False:
					self.bot_neg_keywords.reverse()
					random.shuffle(self.bot_neg_keywords)
					self.telegram_bot.sendMessage(chat_id,random.choice(self.bot_neg_keywords).title())
					self.bot_neg_count+=1

				else:
					self.telegram_bot.sendMessage(chat_id,"🙄🤔 Sorry What Was That, I'm Only Able To Understand Meaningful Text Content Type At The Moment !")


				#-------------
				# DEBUG 
				#-------------
				print "--- DEBUG FOR => INTENT, ACTION, SENTIMENT SCORE ---"
				print '\n'
				print '@'*50
				pprint(intent_handler)
				print '@'*50
				print '\n\n'
				#---------------
				print "--- DEBUG FOR => VALUES ---"
				print '\n'
				print '#'*50
				# Send Debug To Client View As MSG
				# pprint(self.telegram_bot.sendMessage(chat_id,intent_handler))
				print "Table Type : "+self.book_table_type
				print "Total Guest : "+self.book_table
				print "Booking Time : "+self.booking_time
				print "User Phone : "+self.user_phone
				print "User Email : "+self.user_email
				print "User Update : "+str(self.update)+ " | Temp Holder : "+str(self.temp_holder)
				print "\nUser Cancel : "+str(self.cancel_order)
				print '#'*50
				print "\n\n"
				#-------------------

			except IndexError:
				pass
			except TypeError:
				self.telegram_bot.sendMessage(chat_id,"🙄🤔 Sorry What Was That, I'm Only Able To Understand Meaningful Text Content Type At The Moment !")
				pass
			except Exception,e:
				self.log.exception(e)
				print '-'*60
				traceback.print_exc()
				print '-'*60
				sys.exit(1)


	#---------------------------------------
	# Function = intent_handler
	# Find Sentiments And Polarity To Predict User Mood And Inent
	# @param = msg(string)
	# @return = processed_response(json)
	#---------------------------------------
	def intent_handler(self,msg,intent_parser=True):
		action = []
		response = OrderedDict()
			
		if intent_parser==True:
			try:
				intent = TextBlob(msg['text'].lower())
				for val in intent.tags:
					if val[1] == 'CD' or val[1] == 'NN':
						action.append(val[0])
				str_intent = str(intent).replace('TextBlob("','')
				str_intent = str_intent.replace('")','')
				response['msg_text'] = msg['text'].lower()
				response['intent'] = str_intent
				response['action'] = sorted(action)
				response['intent_type'] = self.trainer.classify(intent)
				response['intent_score'] = round(self.trainer.prob_classify(intent).prob(self.trainer.prob_classify(intent).max()),2)
				response['sentiment_score'] = intent.sentiment.polarity
				response = json.dumps({'intent_parsed':True,'agent_response':response})
				return response	
			except KeyError:
				pass

		else:
			response['msg_text'] = msg['text'].lower()
			response = json.dumps({'intent_parsed':False,'agent_response':response})
			return response


	#---------------------------------------
	# Function = send_mail
	# Function To Send Mail Via SMTP Protocol
	# @param = recipient(string),data(string)
	# @return = None
	#---------------------------------------
	def send_mail(self,recipient,data):
		if recipient:
			mail = smtplib.SMTP(self.smtp_server,self.smtp_port)
			login = self.smtp_email
			_pass = self.smtp_pass
			subject = 'Booking Confirmation Receipt From %s'%(self.hotel_name)
			_from = '"Booking Agent Bot" <%s>'%(login)
			mail.ehlo()
			mail.starttls()
			mail.login(login,_pass)
			subject = str(subject)
			reply_to = _from
			preamble = subject
			html = data
			html_content = MIMEText(html,'html')
			msg = MIMEMultipart('alternative')
			msg['Subject'] = subject
			msg['From'] = _from
			msg['Reply-to'] = _from
			msg['To'] = recipient		
			self.log.info("Sending Email To : %s"%(recipient))
			msg.attach(html_content)
			mail.sendmail(_from,recipient,msg.as_string())
			self.log.info("Email Sent : %s"%(recipient))
			mail.close()
			return None


	#---------------------------------------
	# Function = telegram_start
	# Start Telegram via Telepot
	# @param = None
	# @return = None
	#---------------------------------------
	def telegram_start(self):
		MessageLoop(self.telegram_bot, self.telegram_handler).run_as_thread()
		print ('\n\n\n*** AGENT RUNNING ***')
		while True:
			time.sleep(10)


	def credits(self):
		credit_str = '| Author : MR. KEYUR ( MAVERICK ) BHATT | Email : mkbhatt99 [at] gmail [dot] com | Website : http://mkbhatt.herokuapp.com |'
		print "*"*len(credit_str)
		print credit_str
		print "*"*len(credit_str)
		print '\n\n'



#-------------------------------------------------------------

if __name__ == "__main__":
	agent = BookingAgent(settings['agent']['training_data'], settings['agent']['smtp_email'], settings['agent']['smtp_pass'], settings['agent']['smtp_server'], settings['agent']['smtp_port'], settings['agent']['telegram_bot_token'])
	agent.credits()
	agent.telegram_start()



