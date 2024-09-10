BEGIN TRANSACTION;
CREATE TABLE IF NOT EXISTS "ads" (
	"id"	INTEGER,
	"name"	TEXT NOT NULL,
	"link"	TEXT NOT NULL,
	"time"	INTEGER NOT NULL,
	"start"	INTEGER NOT NULL,
	"end"	INTEGER NOT NULL,
	"approve"	INTEGER NOT NULL DEFAULT 0,
	"user"	INTEGER NOT NULL DEFAULT 0,
	PRIMARY KEY("id")
);
CREATE TABLE IF NOT EXISTS "price" (
	"id"	INTEGER NOT NULL DEFAULT 1 UNIQUE,
	"name"	TEXT NOT NULL DEFAULT 'BTC',
	"value"	REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS "config" (
	"value"	TEXT,
	"key"	TEXT
);
CREATE TABLE IF NOT EXISTS "proxy" (
	"link"	TEXT NOT NULL,
	"work"	INTEGER NOT NULL DEFAULT 0,
	"version"	TEXT NOT NULL DEFAULT ipv4
);
CREATE TABLE IF NOT EXISTS "cache" (
	"user_id"	INTEGER NOT NULL,
	"name"	INTEGER,
	"value"	TEXT
);
CREATE TABLE IF NOT EXISTS "senders" (
	"id"	INTEGER NOT NULL UNIQUE,
	"collection_address"	TEXT,
	"telegram_id"	INTEGER,
	"last_time"	INTEGER NOT NULL DEFAULT 0,
	"telegram_user"	INTEGER DEFAULT 0,
	"language"	INTEGER DEFAULT 'en',
	"timezone"	INTEGER DEFAULT 0,
	"name"	TEXT,
	"topic_id"	INTEGER DEFAULT -1,
	PRIMARY KEY("id" AUTOINCREMENT)
);
CREATE TABLE IF NOT EXISTS "topics" (
	"id"	INTEGER UNIQUE,
	"thread_id"	INTEGER,
	"chat_id"	INTEGER,
	"name"	TEXT NOT NULL,
	PRIMARY KEY("id" AUTOINCREMENT)
);
INSERT INTO "config" ("value","key") 
VALUES 
 ('bot_api','https://t.me/BotFather'),
 ('ton_api','https://tonconsole.com/'),
 ('cmc_api','https://pro.coinmarketcap.com/login/'),
 ('dev','your_telegram_id'),
 ('now','0');
COMMIT;
