import asyncio
import json
import os
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.error import BadRequest

# Конфигурация
ADMIN_ID = 8768026303  # ID админа
BOT_TOKEN = "8590462841:AAEcwVDSpmsF0-bqupSureh2RgF-Bnqdde0"
REQUIRED_CHANNEL = "@devgmailbot"

class UserData:
    def __init__(self):
        self.users_file = "bot_users.json"
        self.public_accounts_file = "public_accounts.json"
        self.users = self.load_users()
        self.public_accounts = self.load_public_accounts()
        
    def load_users(self) -> Dict:
        """Загрузить данные пользователей"""
        try:
            if os.path.exists(self.users_file):
                with open(self.users_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Ошибка загрузки пользователей: {e}")
        return {}
        
    def load_public_accounts(self) -> List:
        """Загрузить публичные аккаунты"""
        try:
            if os.path.exists(self.public_accounts_file):
                with open(self.public_accounts_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Ошибка загрузки публичных аккаунтов: {e}")
        return []
        
    def save_users(self):
        """Сохранить данные пользователей"""
        try:
            with open(self.users_file, 'w', encoding='utf-8') as f:
                json.dump(self.users, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения пользователей: {e}")
            
    def save_public_accounts(self):
        """Сохранить публичные аккаунты"""
        try:
            with open(self.public_accounts_file, 'w', encoding='utf-8') as f:
                json.dump(self.public_accounts, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения публичных аккаунтов: {e}")
            
    def is_admin(self, user_id: int) -> bool:
        """Проверить, является ли пользователь админом"""
        return user_id == ADMIN_ID
        
    def has_subscription(self, user_id: int) -> bool:
        """Проверить, есть ли у пользователя активная подписка"""
        user_id_str = str(user_id)
        if user_id_str not in self.users:
            self.users[user_id_str] = {}
            self.save_users()
            return False
            
        user = self.users[user_id_str]
        if not user.get('subscription_until'):
            return False
            
        try:
            sub_until = datetime.fromisoformat(user['subscription_until'])
            return datetime.now() < sub_until
        except:
            return False
            
    def can_use_bot(self, user_id: int) -> bool:
        """Проверить, может ли пользователь использовать бота"""
        return self.is_admin(user_id) or self.has_subscription(user_id)
        
    def add_subscription(self, user_id: int, days: int = 30) -> bool:
        """Добавить подписку пользователю"""
        user_id_str = str(user_id)
        
        if user_id_str not in self.users:
            self.users[user_id_str] = {}
            
        current_sub = self.users[user_id_str].get('subscription_until')
        if current_sub:
            try:
                current_date = datetime.fromisoformat(current_sub)
                if current_date > datetime.now():
                    new_date = current_date + timedelta(days=days)
                else:
                    new_date = datetime.now() + timedelta(days=days)
            except:
                new_date = datetime.now() + timedelta(days=days)
        else:
            new_date = datetime.now() + timedelta(days=days)
            
        self.users[user_id_str]['subscription_until'] = new_date.isoformat()
        self.save_users()
        return True
        
    def get_subscription_info(self, user_id: int) -> Optional[str]:
        """Получить информацию о подписке"""
        user_id_str = str(user_id)
        if user_id_str not in self.users:
            self.users[user_id_str] = {}
            self.save_users()
            return None
            
        sub_until = self.users[user_id_str].get('subscription_until')
        if not sub_until:
            return None
            
        try:
            date = datetime.fromisoformat(sub_until)
            return date.strftime("%d.%m.%Y %H:%M")
        except:
            return None
            
    def get_all_users(self) -> List[Dict]:
        """Получить список всех пользователей"""
        result = []
        for user_id, data in self.users.items():
            result.append({
                'user_id': int(user_id),
                'subscription_until': data.get('subscription_until'),
                'has_active_sub': self.has_subscription(int(user_id))
            })
        return result

    def save_gmail_account(self, user_id: int, email: str, password: str, is_public: bool = False):
        """Сохранить Gmail аккаунт пользователя"""
        user_id_str = str(user_id)
        if user_id_str not in self.users:
            self.users[user_id_str] = {}
        
        if 'gmail_accounts' not in self.users[user_id_str]:
            self.users[user_id_str]['gmail_accounts'] = []
        
        existing_accounts = self.users[user_id_str]['gmail_accounts']
        for account in existing_accounts:
            if account['email'] == email:
                account['password'] = password
                account['is_public'] = is_public
                account['updated_date'] = datetime.now().isoformat()
                self.save_users()
                
                if is_public:
                    self.add_to_public_accounts(email, user_id)
                else:
                    self.remove_from_public_accounts(email)
                return
        
        new_account = {
            'email': email,
            'password': password,
            'is_public': is_public,
            'added_date': datetime.now().isoformat(),
            'updated_date': datetime.now().isoformat()
        }
        
        self.users[user_id_str]['gmail_accounts'].append(new_account)
        self.save_users()
        
        if is_public:
            self.add_to_public_accounts(email, user_id)

    def add_to_public_accounts(self, email: str, owner_id: int):
        """Добавить аккаунт в публичный список"""
        for account in self.public_accounts:
            if account['email'] == email:
                return
                
        self.public_accounts.append({
            'email': email,
            'owner_id': owner_id,
            'added_date': datetime.now().isoformat()
        })
        self.save_public_accounts()

    def remove_from_public_accounts(self, email: str):
        """Удалить аккаунт из публичного списка"""
        self.public_accounts = [acc for acc in self.public_accounts if acc['email'] != email]
        self.save_public_accounts()

    def get_gmail_accounts(self, user_id: int) -> List[Dict]:
        """Получить список Gmail аккаунтов пользователя"""
        user_id_str = str(user_id)
        if user_id_str not in self.users:
            self.users[user_id_str] = {}
            self.save_users()
            return []
        
        return self.users[user_id_str].get('gmail_accounts', [])

    def get_public_accounts(self) -> List[Dict]:
        """Получить список публичных аккаунтов"""
        return self.public_accounts

    def get_gmail_account(self, user_id: int, email: str) -> Optional[Dict]:
        """Получить конкретный Gmail аккаунт"""
        accounts = self.get_gmail_accounts(user_id)
        for account in accounts:
            if account['email'] == email:
                return account
        return None

    def get_account_password(self, email: str) -> Optional[str]:
        """Получить пароль аккаунта по email"""
        for user_id, user_data in self.users.items():
            if 'gmail_accounts' in user_data:
                for account in user_data['gmail_accounts']:
                    if account['email'] == email:
                        return account['password']
        return None

class GmailBot:
    def __init__(self):
        self.user_data = UserData()
        self.user_sessions = {}
        
    async def check_channel_subscription(self, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
        return True
        
    def get_session(self, user_id: int) -> Dict:
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {}
        return self.user_sessions[user_id]
        
    def clear_session(self, user_id: int):
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]
            
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name or "Пользователь"
        
        if not self.user_data.can_use_bot(user_id):
            await update.message.reply_text(
                "❌ У вас нет активной подписки для использования бота.\n\n"
                "📧 Этот бот предназначен для отправки email через Gmail.\n"
                "💎 Для получения доступа свяжитесь с администратором."
            )
            return
            
        if self.user_data.is_admin(user_id):
            status = "👑 Администратор"
        else:
            sub_info = self.user_data.get_subscription_info(user_id)
            status = f"💎 Подписка до: {sub_info}" if sub_info else "❌ Нет подписки"
            
        keyboard = [
            [InlineKeyboardButton("📧 Отправить письмо", callback_data="send_email")],
            [InlineKeyboardButton("⚙️ Настроить Gmail", callback_data="setup_gmail")],
            [InlineKeyboardButton("📋 Мои Gmail аккаунты", callback_data="my_accounts")],
            [InlineKeyboardButton("🌐 Публичные аккаунты", callback_data="public_accounts")],
            [InlineKeyboardButton("ℹ️ Мой статус", callback_data="my_status")]
        ]
        
        if self.user_data.is_admin(user_id):
            keyboard.append([InlineKeyboardButton("👑 Админ панель", callback_data="admin_panel")])
            
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"🚀 Добро пожаловать, {user_name}!\n\n"
            f"📧 Gmail отправщик писем\n"
            f"👤 Статус: {status}\n\n"
            f"Выберите действие:",
            reply_markup=reply_markup
        )
        
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user_id = query.from_user.id
        data = query.data
        
        await query.answer()
        
        public_sections = ["public_accounts"]
        if not self.user_data.can_use_bot(user_id) and data not in public_sections and not data.startswith("admin"):
            try:
                await query.edit_message_text(
                    "❌ У вас нет активной подписки для использования этой функции."
                )
            except BadRequest:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="❌ У вас нет активной подписки для использования этой функции."
                )
            return
        
        try:
            if data == "send_email":
                await self.start_email_process(query)
            elif data == "setup_gmail":
                await self.setup_gmail_process(query)
            elif data == "my_accounts":
                await self.show_my_accounts(query)
            elif data == "public_accounts":
                await self.show_public_accounts(query)
            elif data.startswith("select_account_"):
                await self.select_account(query, data)
            elif data.startswith("select_public_"):
                await self.select_public_account(query, data)
            elif data.startswith("privacy_"):
                await self.handle_privacy_selection(query, data)
            elif data == "my_status":
                await self.show_user_status(query)
            elif data == "admin_panel" and self.user_data.is_admin(user_id):
                await self.show_admin_panel(query)
            elif data.startswith("admin_") and self.user_data.is_admin(user_id):
                await self.handle_admin_action(query, data)
            elif data == "back_to_main":
                await self.back_to_main(query)
            elif data == "cancel_action":
                await self.cancel_current_action(query)
            elif data == "confirm_send":
                await self.confirm_send_email(query)
        except Exception as e:
            print(f"Ошибка в обработке callback: {e}")
            await query.edit_message_text("❌ Произошла ошибка. Попробуйте снова.")

    async def show_my_accounts(self, query):
        user_id = query.from_user.id
        accounts = self.user_data.get_gmail_accounts(user_id)
        
        if not accounts:
            keyboard = [
                [InlineKeyboardButton("⚙️ Добавить Gmail аккаунт", callback_data="setup_gmail")],
                [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "📋 У вас нет сохраненных Gmail аккаунтов\n\n"
                "Добавьте свой первый аккаунт:",
                reply_markup=reply_markup
            )
            return
        
        text = "📋 Ваши Gmail аккаунты:\n\n"
        keyboard = []
        
        for i, account in enumerate(accounts):
            email = account['email']
            status = "🌐 Публичный" if account.get('is_public', False) else "🔒 Приватный"
            added_date = datetime.fromisoformat(account['added_date']).strftime("%d.%m.%Y")
            text += f"{i+1}. {email}\n   Статус: {status}\n   Добавлен: {added_date}\n\n"
            keyboard.append([InlineKeyboardButton(f"📧 {email}", callback_data=f"select_account_{i}")])
        
        keyboard.append([InlineKeyboardButton("➕ Добавить новый аккаунт", callback_data="setup_gmail")])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text + "Выберите аккаунт для отправки или добавьте новый:",
            reply_markup=reply_markup
        )

    async def show_public_accounts(self, query):
        public_accounts = self.user_data.get_public_accounts()
        
        if not public_accounts:
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "🌐 Публичные аккаунты\n\n"
                "❌ Нет доступных публичных аккаунтов",
                reply_markup=reply_markup
            )
            return
        
        text = "🌐 Доступные публичные аккаунты:\n\n"
        keyboard = []
        
        for i, account in enumerate(public_accounts):
            email = account['email']
            added_date = datetime.fromisoformat(account['added_date']).strftime("%d.%m.%Y")
            text += f"{i+1}. {email}\n   Добавлен: {added_date}\n\n"
            keyboard.append([InlineKeyboardButton(f"📧 {email}", callback_data=f"select_public_{i}")])
        
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text + "Выберите аккаунт для отправки:",
            reply_markup=reply_markup
        )

    async def select_account(self, query, data):
        user_id = query.from_user.id
        try:
            account_index = int(data.split("_")[-1])
            accounts = self.user_data.get_gmail_accounts(user_id)
            
            if account_index >= len(accounts):
                await query.edit_message_text("❌ Аккаунт не найден")
                return
            
            account = accounts[account_index]
            session = self.get_session(user_id)
            session['gmail_email'] = account['email']
            session['gmail_password'] = account['password']
            session['step'] = 'email_recipients'
            
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="my_accounts")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"✅ Выбран ваш аккаунт: {account['email']}\n\n"
                "📝 Введите email получателей.\n"
                "💡 Можно несколько через запятую:\n"
                "example1@gmail.com, example2@mail.ru\n\n"
                "📎 Или отправьте TXT файл с email адресами (каждый с новой строки)",
                reply_markup=reply_markup
            )
        except Exception as e:
            await query.edit_message_text("❌ Ошибка при выборе аккаунта")

    async def select_public_account(self, query, data):
        user_id = query.from_user.id
        try:
            account_index = int(data.split("_")[-1])
            public_accounts = self.user_data.get_public_accounts()
            
            if account_index >= len(public_accounts):
                await query.edit_message_text("❌ Аккаунт не найден")
                return
            
            account = public_accounts[account_index]
            email = account['email']
            
            password = self.user_data.get_account_password(email)
            if not password:
                await query.edit_message_text("❌ Ошибка: пароль аккаунта не найден")
                return
            
            session = self.get_session(user_id)
            session['gmail_email'] = email
            session['gmail_password'] = password
            session['step'] = 'email_recipients'
            
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="public_accounts")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"✅ Выбран публичный аккаунт: {email}\n\n"
                "📝 Введите email получателей.\n"
                "💡 Можно несколько через запятую:\n"
                "example1@gmail.com, example2@mail.ru\n\n"
                "📎 Или отправьте TXT файл с email адресами (каждый с новой строки)",
                reply_markup=reply_markup
            )
        except Exception as e:
            await query.edit_message_text("❌ Ошибка при выборе аккаунта")

    async def setup_gmail_process(self, query):
        user_id = query.from_user.id
        session = self.get_session(user_id)
        session['step'] = 'gmail_email'
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "⚙️ Настройка Gmail\n\n"
            "📧 Введите ваш Gmail адрес:",
            reply_markup=reply_markup
        )

    async def handle_privacy_selection(self, query, data):
        user_id = query.from_user.id
        session = self.get_session(user_id)
        
        is_public = data == "privacy_public"
        email = session.get('gmail_email')
        password = session.get('gmail_password')
        
        if email and password:
            self.user_data.save_gmail_account(user_id, email, password, is_public)
            session['step'] = None
            
            status = "🌐 публичным" if is_public else "🔒 приватным"
            keyboard = [[InlineKeyboardButton("🔙 В меню", callback_data="back_to_main")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"✅ Gmail аккаунт сохранен как {status}!\n\n"
                f"📧 Email: {email}\n"
                f"🔐 Пароль сохранен и скрыт для безопасности.\n\n"
                f"📧 Теперь можете отправлять письма!",
                reply_markup=reply_markup
            )
        else:
            await query.edit_message_text("❌ Ошибка: данные аккаунта не найдены")

    async def handle_gmail_email(self, update: Update, email: str):
        user_id = update.effective_user.id
        session = self.get_session(user_id)
        
        if '@gmail.com' not in email.lower():
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "❌ Введите корректный Gmail адрес (@gmail.com)",
                reply_markup=reply_markup
            )
            return
            
        session['gmail_email'] = email.strip()
        session['step'] = 'gmail_password'
        
        keyboard = [[InlineKeyboardButton("❌ Отменить", callback_data="cancel_action")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ Email принят: {email}\n\n"
            f"🔐 Теперь введите App Password.\n\n"
            f"⚠️ ВАЖНО: Нужен App Password (16 символов), не обычный пароль!\n"
            f"📋 Как получить:\n"
            f"1. Откройте: myaccount.google.com/security\n"
            f"2. Включите 2FA\n"
            f"3. Создайте App Password для Mail\n"
            f"4. Введите полученный код",
            reply_markup=reply_markup
        )
        
    async def handle_gmail_password(self, update: Update, password: str):
        user_id = update.effective_user.id
        session = self.get_session(user_id)
        
        password = password.strip().replace(" ", "")
        
        if len(password) != 16:
            keyboard = [[InlineKeyboardButton("❌ Отменить", callback_data="cancel_action")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"❌ App Password должен быть 16 символов.\n"
                f"Получено: {len(password)} символов",
                reply_markup=reply_markup
            )
            return
        
        session['gmail_password'] = password
        
        email = session['gmail_email']
        keyboard = [
            [InlineKeyboardButton("🌐 Сделать публичным", callback_data="privacy_public")],
            [InlineKeyboardButton("🔒 Оставить приватным", callback_data="privacy_private")],
            [InlineKeyboardButton("❌ Отменить", callback_data="cancel_action")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ App Password принят!\n\n"
            f"📧 Email: {email}\n\n"
            f"🌐 Хотите сделать этот аккаунт публичным?\n"
            f"• 🌐 Публичный - другие пользователи смогут видеть и использовать ваш email\n"
            f"• 🔒 Приватный - только вы будете видеть этот аккаунт\n\n"
            f"Выберите вариант:",
            reply_markup=reply_markup
        )
        
        try:
            await update.message.delete()
        except:
            pass

    async def start_email_process(self, query):
        user_id = query.from_user.id
        
        keyboard = [
            [InlineKeyboardButton("📋 Мои аккаунты", callback_data="my_accounts")],
            [InlineKeyboardButton("🌐 Публичные аккаунты", callback_data="public_accounts")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📧 Отправка письма\n\n"
            "Выберите откуда взять Gmail аккаунт:",
            reply_markup=reply_markup
        )

    async def show_user_status(self, query):
        user_id = query.from_user.id
        
        if self.user_data.is_admin(user_id):
            status_text = "👑 Ваш статус: Администратор\n\n🔓 У вас полный доступ ко всем функциям бота"
        else:
            sub_info = self.user_data.get_subscription_info(user_id)
            if sub_info:
                status_text = f"💎 Ваш статус: Подписчик\n\n⏰ Подписка активна до: {sub_info}"
            else:
                status_text = "❌ У вас нет активной подписки"
                
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(status_text, reply_markup=reply_markup)

    async def show_admin_panel(self, query):
        """Показать админ панель"""
        keyboard = [
            [InlineKeyboardButton("👥 Список пользователей", callback_data="admin_users")],
            [InlineKeyboardButton("💎 Добавить подписку", callback_data="admin_add_sub")],
            [InlineKeyboardButton("❌ Отменить подписку", callback_data="admin_cancel_sub")],
            [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "👑 Админ панель\n\n"
            "Выберите действие:",
            reply_markup=reply_markup
        )
        
    async def handle_admin_action(self, query, data):
        """Обработка админских действий"""
        if data == "admin_users":
            await self.show_users_list(query)
        elif data == "admin_add_sub":
            await self.start_add_subscription(query)
        elif data == "admin_cancel_sub":
            await self.start_cancel_subscription(query)
        elif data == "admin_stats":
            await self.show_statistics(query)
            
    async def show_users_list(self, query):
        """Показать список пользователей"""
        users = self.user_data.get_all_users()
        
        if not users:
            text = "👥 Пользователи не найдены"
        else:
            text = "👥 Список пользователей:\n\n"
            for user in users:
                user_id = user['user_id']
                if user['has_active_sub']:
                    sub_info = self.user_data.get_subscription_info(user_id)
                    status = f"💎 до {sub_info}" if sub_info else "💎 активная подписка"
                else:
                    status = "❌ нет подписки"
                    
                text += f"🆔 {user_id}\n📋 {status}\n\n"
                
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup)
        
    async def start_add_subscription(self, query):
        """Начать добавление подписки"""
        user_id = query.from_user.id
        session = self.get_session(user_id)
        session['step'] = 'admin_add_sub_id'
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "💎 Добавление подписки\n\n"
            "🆔 Введите ID пользователя:",
            reply_markup=reply_markup
        )
        
    async def start_cancel_subscription(self, query):
        """Начать отмену подписки"""
        user_id = query.from_user.id
        session = self.get_session(user_id)
        session['step'] = 'admin_cancel_sub_id'
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "❌ Отмена подписки\n\n"
            "🆔 Введите ID пользователя для отмены подписки:",
            reply_markup=reply_markup
        )
        
    async def show_statistics(self, query):
        """Показать статистику"""
        users = self.user_data.get_all_users()
        total_users = len(users)
        active_subs = sum(1 for user in users if user['has_active_sub'])
        
        text = (
            f"📊 Статистика бота\n\n"
            f"👥 Всего пользователей: {total_users}\n"
            f"💎 Активных подписок: {active_subs}\n"
            f"❌ Без подписки: {total_users - active_subs}"
        )
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup)

    async def back_to_main(self, query):
        user_id = query.from_user.id
        user_name = query.from_user.first_name or "Пользователь"
        
        if self.user_data.is_admin(user_id):
            status = "👑 Администратор"
        else:
            sub_info = self.user_data.get_subscription_info(user_id)
            status = f"💎 Подписка до: {sub_info}" if sub_info else "❌ Нет подписки"
            
        keyboard = [
            [InlineKeyboardButton("📧 Отправить письмо", callback_data="send_email")],
            [InlineKeyboardButton("⚙️ Настроить Gmail", callback_data="setup_gmail")],
            [InlineKeyboardButton("📋 Мои Gmail аккаунты", callback_data="my_accounts")],
            [InlineKeyboardButton("🌐 Публичные аккаунты", callback_data="public_accounts")],
            [InlineKeyboardButton("ℹ️ Мой статус", callback_data="my_status")]
        ]
        
        if self.user_data.is_admin(user_id):
            keyboard.append([InlineKeyboardButton("👑 Админ панель", callback_data="admin_panel")])
            
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.edit_message_text(
                f"🚀 Gmail отправщик писем\n\n"
                f"👤 {user_name}\n"
                f"📋 Статус: {status}\n\n"
                f"Выберите действие:",
                reply_markup=reply_markup
            )
        except Exception as e:
            print(f"Ошибка при возврате в главное меню: {e}")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текстовых сообщений"""
        user_id = update.effective_user.id
        text = update.message.text
        
        if not self.user_data.can_use_bot(user_id):
            await update.message.reply_text(
                "❌ У вас нет активной подписки для использования бота"
            )
            return
            
        session = self.get_session(user_id)
        step = session.get('step')
        
        if step == 'gmail_email':
            await self.handle_gmail_email(update, text)
        elif step == 'gmail_password':
            await self.handle_gmail_password(update, text)
        elif step == 'email_recipients':
            await self.handle_email_recipients(update, text)
        elif step == 'email_subject':
            await self.handle_email_subject(update, text)
        elif step == 'email_body':
            await self.handle_email_body(update, text)
        elif step == 'admin_add_sub_id':
            await self.handle_admin_sub_id(update, text)
        elif step == 'admin_add_sub_days':
            await self.handle_admin_sub_days(update, text)
        elif step == 'admin_cancel_sub_id':
            await self.handle_admin_cancel_sub_id(update, text)
        else:
            await update.message.reply_text(
                "Используйте /start для начала работы\n\n"
                "Или нажмите кнопку 'Назад' если она есть."
            )

    async def handle_txt_file(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка TXT файла с email адресами"""
        user_id = update.effective_user.id
        
        if not self.user_data.can_use_bot(user_id):
            await update.message.reply_text("❌ У вас нет активной подписки")
            return
            
        session = self.get_session(user_id)
        if session.get('step') != 'email_recipients':
            await update.message.reply_text("❌ Сначала выберите аккаунт для отправки")
            return
            
        try:
            file = await context.bot.get_file(update.message.document.file_id)
            file_bytes = await file.download_as_bytearray()
            content = file_bytes.decode('utf-8')
            
            emails = []
            for line in content.splitlines():
                line_emails = [email.strip() for email in line.split(',') if email.strip()]
                emails.extend(line_emails)
                
            if not emails:
                await update.message.reply_text("❌ В файле не найдено email адресов")
                return
                
            session['email_recipients'] = emails
            session['step'] = 'email_subject'
            
            keyboard = [[InlineKeyboardButton("❌ Отменить", callback_data="cancel_action")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"✅ Загружено {len(emails)} email адресов из файла\n\n"
                f"📋 Теперь введите заголовок письма:",
                reply_markup=reply_markup
            )
            
        except Exception as e:
            print(f"Ошибка обработки файла: {e}")
            await update.message.reply_text("❌ Ошибка обработки файла")

    async def handle_email_recipients(self, update: Update, recipients: str):
        user_id = update.effective_user.id
        session = self.get_session(user_id)
        
        emails = [email.strip() for email in recipients.split(',')]
        emails = [email for email in emails if email and '@' in email]
        
        if not emails:
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("❌ Не найдено валидных email адресов", reply_markup=reply_markup)
            return
            
        session['email_recipients'] = emails
        session['step'] = 'email_subject'
        
        keyboard = [[InlineKeyboardButton("❌ Отменить", callback_data="cancel_action")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ Получатели ({len(emails)}):\n{chr(10).join('• ' + email for email in emails)}\n\n📋 Теперь введите заголовок письма:",
            reply_markup=reply_markup
        )
        
    async def handle_email_subject(self, update: Update, subject: str):
        user_id = update.effective_user.id
        session = self.get_session(user_id)
        session['email_subject'] = subject.strip()
        session['step'] = 'email_body'
        
        keyboard = [[InlineKeyboardButton("❌ Отменить", callback_data="cancel_action")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(f"✅ Заголовок: {subject}\n\n📝 Теперь введите текст письма:", reply_markup=reply_markup)
        
    async def handle_email_body(self, update: Update, body: str):
        user_id = update.effective_user.id
        session = self.get_session(user_id)
        session['email_body'] = body.strip()
        
        recipients = session['email_recipients']
        subject = session['email_subject']
        
        keyboard = [
            [InlineKeyboardButton("✅ Отправить", callback_data="confirm_send")],
            [InlineKeyboardButton("❌ Отмена", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        preview = (
            f"👀 Предпросмотр письма:\n\n"
            f"📧 От: {session['gmail_email']}\n"
            f"👥 Кому: {', '.join(recipients[:3])}{'...' if len(recipients) > 3 else ''}\n"
            f"📋 Заголовок: {subject}\n"
            f"📝 Текст: {body[:200]}{'...' if len(body) > 200 else ''}\n\n"
            f"Отправить письмо?"
        )
        
        await update.message.reply_text(preview, reply_markup=reply_markup)
        
    async def confirm_send_email(self, query):
        user_id = query.from_user.id
        await query.edit_message_text("📤 Отправка письма... Пожалуйста, подождите...")
        result = await self.send_email_actual(user_id)
        self.clear_session(user_id)
        
        keyboard = [[InlineKeyboardButton("🔙 В меню", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(result, reply_markup=reply_markup)
        
    async def send_email_actual(self, user_id: int) -> str:
        session = self.get_session(user_id)
        
        try:
            email = session['gmail_email']
            password = session['gmail_password']
            recipients = session['email_recipients']
            subject = session['email_subject']
            body = session['email_body']
            
            msg = MIMEMultipart()
            msg['From'] = email
            msg['To'] = ', '.join(recipients)
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))
            
            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.starttls()
                server.login(email, password)
                
                success_count = 0
                failed_recipients = []
                
                for recipient in recipients:
                    try:
                        server.sendmail(email, [recipient], msg.as_string())
                        success_count += 1
                    except Exception as e:
                        failed_recipients.append(f"{recipient}: {str(e)[:50]}")
                
            result = (
                f"📊 Результат отправки:\n\n"
                f"✅ Успешно отправлено: {success_count} из {len(recipients)}\n"
            )
            
            if failed_recipients:
                result += f"\n❌ Ошибки отправки:\n" + "\n".join(failed_recipients[:3])
                if len(failed_recipients) > 3:
                    result += f"\n... и еще {len(failed_recipients) - 3} ошибок"
                
            return result
            
        except smtplib.SMTPAuthenticationError:
            return (
                "❌ Ошибка аутентификации!\n\n"
                "Проверьте:\n"
                "• Правильность App Password\n"
                "• Включена ли 2FA в Google\n"
                "• Создан ли App Password для Mail"
            )
        except smtplib.SMTPException as e:
            return f"❌ Ошибка SMTP: {str(e)}"
        except Exception as e:
            return f"❌ Общая ошибка отправки: {str(e)}"
            
    async def handle_admin_sub_id(self, update: Update, user_id_text: str):
        """Обработка ID для подписки"""
        admin_id = update.effective_user.id
        session = self.get_session(admin_id)
        
        try:
            target_user_id = int(user_id_text.strip())
            session['target_user_id'] = target_user_id
            session['step'] = 'admin_add_sub_days'
            
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"✅ ID пользователя: {target_user_id}\n\n"
                f"📅 Введите количество дней подписки:",
                reply_markup=reply_markup
            )
        except ValueError:
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "❌ Введите корректный числовой ID",
                reply_markup=reply_markup
            )
            
    async def handle_admin_sub_days(self, update: Update, days_text: str):
        """Обработка количества дней подписки"""
        admin_id = update.effective_user.id
        session = self.get_session(admin_id)
        
        try:
            days = int(days_text.strip())
            target_user_id = session['target_user_id']
            
            if days <= 0:
                keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    "❌ Количество дней должно быть больше 0",
                    reply_markup=reply_markup
                )
                return
                
            self.user_data.add_subscription(target_user_id, days)
            session['step'] = None
            
            keyboard = [[InlineKeyboardButton("🔙 В админ панель", callback_data="admin_panel")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"✅ Подписка добавлена!\n\n"
                f"👤 Пользователь: {target_user_id}\n"
                f"📅 Дней: {days}",
                reply_markup=reply_markup
            )
            
        except ValueError:
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "❌ Введите корректное количество дней",
                reply_markup=reply_markup
            )

    async def handle_admin_cancel_sub_id(self, update: Update, user_id_text: str):
        """Обработка отмены подписки"""
        admin_id = update.effective_user.id
        session = self.get_session(admin_id)
        
        try:
            target_user_id = int(user_id_text.strip())
            user_id_str = str(target_user_id)
            
            if user_id_str not in self.user_data.users:
                keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    f"❌ Пользователь {target_user_id} не найден",
                    reply_markup=reply_markup
                )
                return
                
            if 'subscription_until' in self.user_data.users[user_id_str]:
                del self.user_data.users[user_id_str]['subscription_until']
                self.user_data.save_users()
                
            session['step'] = None
            
            keyboard = [[InlineKeyboardButton("🔙 В админ панель", callback_data="admin_panel")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"✅ Подписка отменена!\n\n"
                f"👤 Пользователь: {target_user_id}\n"
                f"📋 Подписка удалена",
                reply_markup=reply_markup
            )
            
        except ValueError:
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "❌ Введите корректный числовой ID",
                reply_markup=reply_markup
            )
            
    async def cancel_current_action(self, query):
        user_id = query.from_user.id
        self.clear_session(user_id)
        await self.back_to_main(query)
        
    def run(self):
        application = Application.builder().token(BOT_TOKEN).build()
        
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CallbackQueryHandler(self.button_callback))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        application.add_handler(MessageHandler(filters.Document.FileExtension("txt"), self.handle_txt_file))
        
        print("🤖 Бот запущен...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    bot = GmailBot()
    bot.run()