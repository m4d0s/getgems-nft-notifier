BEGIN TRANSACTION;

CREATE TABLE
	IF NOT EXISTS "config" (
		"BOT_TOKEN" TEXT NOT NULL DEFAULT 'https://t.me/BotFather',
		"TON_API" TEXT NOT NULL DEFAULT 'https://tonconsole.com/',
		"CMC_API" TEXT NOT NULL DEFAULT 'https://pro.coinmarketcap.com/login/',
		"DB_PATH" INTEGER NOT NULL DEFAULT 'sqlite.db',
		"NOW" INTEGER NOT NULL DEFAULT 0,
		"TON_PRICE" REAL NOT NULL DEFAULT 0.0
	);

CREATE TABLE
	IF NOT EXISTS "ads" (
		"id" INTEGER,
		"name" TEXT NOT NULL,
		"link" TEXT NOT NULL,
		"time" INTEGER NOT NULL,
		"start" INTEGER NOT NULL,
		"end" INTEGER NOT NULL,
		"approve" INTEGER NOT NULL DEFAULT 0,
		PRIMARY KEY ("id")
	);

CREATE TABLE
	IF NOT EXISTS "senders" (
		"collection_address" TEXT NOT NULL,
		"telegram_id" INTEGER NOT NULL,
		"last_time" INTEGER NOT NULL DEFAULT 0,
		"id" INTEGER,
		"telegram_user" INTEGER NOT NULL DEFAULT 0,
		"language" INTEGER NOT NULL DEFAULT 'en',
		PRIMARY KEY ("id")
	);

INSERT INTO
	"ads" (
		"id",
		"name",
		"link",
		"time",
		"start",
		"end",
		"approve"
	)
VALUES
	(
		0,
		'You can place your AD here',
		'{bot.link}',
		0,
		0,
		1.0e+22,
		1
	) COMMIT;