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
CREATE TABLE IF NOT EXISTS "proxy" (
	"link"	TEXT NOT NULL,
	"work"	INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS "config" (
	"value"	TEXT,
	"key"	TEXT
);
CREATE TABLE IF NOT EXISTS "cache" (
	"user_id"	INTEGER NOT NULL UNIQUE,
	"name"	INTEGER,
	"value"	TEXT,
	PRIMARY KEY("user_id")
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
	PRIMARY KEY("id" AUTOINCREMENT)
);
INSERT INTO "ads" ("id","name","link","time","start","end","approve","user") VALUES (0,'-','{bot.link}',0,0,1.0e+22,1,0)
INSERT INTO "config" ("value","key") VALUES 
 ('bot_api','https://t.me/BotFather'),
 ('ton_api','https://tonconsole.com/'),
 ('cmc_api','https://pro.coinmarketcap.com/login/'),
 ('now','0'),
 ('dev','your_telegram_id');
COMMIT;
