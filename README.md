# getgems-nft-notifier
## Created for Luna or Not
 
### What it thing can do?
- Written using [API from Getgems](https://api.getgems.io/graphql ), [TON API](https://tonconsole.com ) and also connected [API from CMC](https://pro.coinmarketcap.com )
- The function of logging all necessary and unnecessary actions to a file (there is still work to be done with the levels of logging)
- There is a block for advertising, you can earn from it or advertise your own project
- Most data is taken from the sqlite database, another from `.json` configs 

### What to do in next updates?
- Relative time and custom timezone
- Setup for other chats
- Booking ad mechanism
- Fix another bugs
- Notification for new bids (maybe, maybe not)

# Installation
- Creating a database using the `sqlite.db.sql` file
- Install Python no earlier than version 3.11.4
- Go to the console, go to the root folder and write the command:
`pip install -r req.txt `
- After that, go to the newly created database and enter the following fields (I advise you to not change the field with the location of the database, it has not fully configured yet, but used somewhere), without these keys, the program will not work correctly ([Recomend to use DB Browser](https://sqlitebrowser.org/dl/)):

![image](https://github.com/user-attachments/assets/9671a5b7-1bfe-4322-b891-c151dff9a9d1)

- Don't forget to read the file `../logs/test.log`, it's important :)
- Finally back to the root folder, open the console and write:
`python main.py `
- Enjoy!

# Some DB explanation
- `config` - like configuration file, input all needed keys in first 3 (4) fields, dont touch other
- `senders` - config for sending notification (what collection, where, by who, last update time and language ("ru" or "en"))
- `ads` for  place your ad. First row used for ad-free form, you can change only name here, but better dont touch. Other rows from another users with date of placing, start/end time, approve status (with 0 it cant be shown)
