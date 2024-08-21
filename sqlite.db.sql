BEGIN TRANSACTION;

CREATE TABLE
	IF NOT EXISTS "ads" (
		"id" INTEGER,
		"name" TEXT NOT NULL,
		"link" TEXT NOT NULL,
		"time" INTEGER NOT NULL,
		"start" INTEGER NOT NULL,
		"end" INTEGER NOT NULL,
		"approve" INTEGER NOT NULL DEFAULT 0,
		"user" INTEGER NOT NULL DEFAULT 0,
		PRIMARY KEY ("id")
	);

CREATE TABLE
	IF NOT EXISTS "config" (
		"BOT_TOKEN" TEXT NOT NULL DEFAULT 'https://t.me/BotFather',
		"TON_API" TEXT NOT NULL DEFAULT 'https://tonconsole.com/',
		"CMC_API" TEXT NOT NULL DEFAULT 'https://pro.coinmarketcap.com/login/',
		"NOW" INTEGER NOT NULL DEFAULT 0
	);

CREATE TABLE
	IF NOT EXISTS "price" (
		"id" INTEGER NOT NULL DEFAULT 1 UNIQUE,
		"name" TEXT NOT NULL DEFAULT 'BTC',
		"value" REAL NOT NULL DEFAULT 0
	);

CREATE TABLE
	IF NOT EXISTS "senders" (
		"collection_address" TEXT NOT NULL,
		"telegram_id" INTEGER NOT NULL,
		"last_time" INTEGER NOT NULL DEFAULT 0,
		"id" INTEGER,
		"telegram_user" INTEGER NOT NULL DEFAULT 0,
		"language" INTEGER NOT NULL DEFAULT 'en',
		"timezone" INTEGER NOT NULL DEFAULT 0,
		"name" TEXT NOT NULL,
		PRIMARY KEY ("id")
	);

CREATE TABLE
	IF NOT EXISTS "proxy" (
		"address" TEXT NOT NULL,
		"port" TEXT NOT NULL,
		"login" TEXT NOT NULL,
		"password" TEXT NOT NULL,
		"protocol" TEXT NOT NULL
	);

INSERT INTO
	"ads" (
		"id",
		"name",
		"link",
		"time",
		"start",
		"end",
		"approve",
		"user"
	)
VALUES
	(0, '-', '{bot.link}', 0, 0, 1.0e+22, 1, 0);

INSERT INTO
	"price" ("id", "name", "value")
VALUES
	(11419, 'TON', 6.45361531735384),
	(28850, 'NOT', 0.0114920690962407),
	(825, 'USDT', 1.00041667119992),
	(1027, 'ETH', 2637.96383948944),
	(1, 'BTC', 60491.4854371469);

COMMIT;