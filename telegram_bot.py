from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
import logging
from decimal import Decimal
import os
from dotenv import load_dotenv
from bot import TradingBot
from signals import generate_trading_signals
import pandas as pd

# Cargar variables de entorno
load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
ALLOWED_USERS = os.getenv('ALLOWED_USERS', '').split(',')

class TelegramTrader:
    def __init__(self):
        self.trading_bot = None
        self.user_wallets = {}  # Almacenar las credenciales de los usuarios
        self.setup_logging()
        self.auto_trading = False
        self.auto_trading_task = None
        
    @staticmethod
    def setup_logging():
        """Configura el sistema de logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando inicial del bot"""
        user_id = str(update.effective_user.id)
        
        if user_id not in self.user_wallets:
            keyboard = [
                [InlineKeyboardButton("🔑 Conectar Cartera", callback_data='connect_wallet')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "👋 ¡Bienvenido al Bot de Trading!\n"
                "Para comenzar, necesitas conectar tu cartera de Hyperliquid.",
                reply_markup=reply_markup
            )
        else:
            await self.show_main_menu(update, context)

    async def connect_wallet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Proceso de conexión de cartera"""
        query = update.callback_query
        user_id = str(query.from_user.id)
        
        # Iniciar conversación para recoger credenciales
        await query.message.reply_text(
            "🔐 Para conectar tu cartera, necesito tu API Key de Hyperliquid.\n"
            "1️⃣ Ve a https://testnet.hyperliquid.xyz\n"
            "2️⃣ Conecta tu wallet\n"
            "3️⃣ Ve a Settings -> API Keys\n"
            "4️⃣ Crea una nueva API key\n"
            "5️⃣ Envíame tu Wallet Address (sin el prefijo 0x)"
        )
        context.user_data['waiting_for'] = 'wallet_address'

    async def handle_wallet_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja la entrada de credenciales de wallet"""
        user_id = str(update.effective_user.id)
        message = update.message.text
        
        if 'waiting_for' not in context.user_data:
            return
            
        if context.user_data['waiting_for'] == 'wallet_address':
            # Guardar wallet address
            context.user_data['wallet_address'] = message
            await update.message.reply_text(
                "✅ Wallet Address recibida.\n"
                "Ahora envíame tu Private Key (sin el prefijo 0x)"
            )
            context.user_data['waiting_for'] = 'private_key'
            
        elif context.user_data['waiting_for'] == 'private_key':
            # Guardar private key y configurar el bot
            try:
                self.user_wallets[user_id] = {
                    'wallet_address': context.user_data['wallet_address'],
                    'private_key': message
                }
                
                # Inicializar el bot de trading para este usuario
                self.trading_bot = self.setup_trading_bot(user_id)
                
                await update.message.reply_text(
                    "🎉 ¡Cartera conectada exitosamente!\n"
                    "Ya puedes comenzar a operar."
                )
                await self.show_main_menu(update, context)
                
            except Exception as e:
                await update.message.reply_text(
                    f"❌ Error conectando la cartera: {str(e)}\n"
                    "Por favor, intenta nuevamente con /start"
                )
            
            # Limpiar datos sensibles
            del context.user_data['waiting_for']
            if 'wallet_address' in context.user_data:
                del context.user_data['wallet_address']

    def setup_trading_bot(self, user_id: str) -> TradingBot:
        """Configura el bot de trading para un usuario específico"""
        credentials = self.user_wallets[user_id]
        return TradingBot(
            api_key=credentials['wallet_address'],
            api_secret=credentials['private_key']
        )

    async def show_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Muestra el menú principal"""
        keyboard = [
            [InlineKeyboardButton("📊 Ver Balance", callback_data='balance')],
            [InlineKeyboardButton("💰 Comprar", callback_data='buy'),
             InlineKeyboardButton("💸 Vender", callback_data='sell')],
            [InlineKeyboardButton("🤖 Trading Automático", callback_data='auto_trading')],
            [InlineKeyboardButton("📈 Ver Señales", callback_data='signals')],
            [InlineKeyboardButton("⚙️ Configuración Cartera", callback_data='wallet_settings')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = (
            "🤖 Bot de Trading Hyperliquid\n"
            "Selecciona una opción:"
        )
        
        if hasattr(update, 'callback_query'):
            await update.callback_query.message.edit_text(message, reply_markup=reply_markup)
        else:
            await update.message.reply_text(message, reply_markup=reply_markup)

    async def auto_trading_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Menú de trading automático"""
        query = update.callback_query
        keyboard = [
            [InlineKeyboardButton(
                "🔴 Detener" if self.auto_trading else "🟢 Iniciar", 
                callback_data='auto_trading_toggle'
            )],
            [InlineKeyboardButton("⚙️ Configuración", callback_data='auto_trading_config')],
            [InlineKeyboardButton("📊 Estado", callback_data='auto_trading_status')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            "🤖 Trading Automático\n"
            f"Estado: {'Activo ✅' if self.auto_trading else 'Inactivo ❌'}",
            reply_markup=reply_markup
        )

    async def toggle_auto_trading(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Activa o desactiva el trading automático"""
        query = update.callback_query
        self.auto_trading = not self.auto_trading
        
        if self.auto_trading:
            await query.message.reply_text("🟢 Trading automático activado")
            self.auto_trading_task = context.job_queue.run_repeating(
                self.auto_trading_cycle, 
                interval=300,  # Cada 5 minutos
                first=1
            )
        else:
            await query.message.reply_text("🔴 Trading automático desactivado")
            if self.auto_trading_task:
                self.auto_trading_task.schedule_removal()

    async def auto_trading_cycle(self, context: ContextTypes.DEFAULT_TYPE):
        """Ciclo de trading automático"""
        try:
            # Obtener señales actuales
            signals = self.trading_bot.get_current_signals()
            
            for asset, signal in signals.items():
                balance = self.trading_bot.get_balance()
                
                if signal == "BUY" and balance['USDT'] > 0:
                    quantity = self.calculate_position_size(balance['USDT'], asset)
                    success = self.trading_bot.execute_market_order(asset, "BUY", quantity)
                    if success:
                        await self.notify_trade(context, "COMPRA", asset, quantity)
                        
                elif signal == "SELL" and balance.get(asset, 0) > 0:
                    quantity = balance[asset]
                    success = self.trading_bot.execute_market_order(asset, "SELL", quantity)
                    if success:
                        await self.notify_trade(context, "VENTA", asset, quantity)
                        
        except Exception as e:
            logging.error(f"Error en ciclo de trading: {str(e)}")
            for user_id in ALLOWED_USERS:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"⚠️ Error en trading automático: {str(e)}"
                )

    async def notify_trade(self, context, action, asset, quantity):
        """Notifica a los usuarios sobre una operación ejecutada"""
        message = (
            f"🤖 Operación Automática Ejecutada\n"
            f"Acción: {action}\n"
            f"Activo: {asset}\n"
            f"Cantidad: {quantity}\n"
            f"Timestamp: {pd.Timestamp.now()}"
        )
        
        for user_id in ALLOWED_USERS:
            await context.bot.send_message(
                chat_id=user_id,
                text=message
            )

    def calculate_position_size(self, available_balance: float, asset: str) -> float:
        """Calcula el tamaño de la posición basado en gestión de riesgo"""
        risk_per_trade = 0.02  # 2% del balance por operación
        return available_balance * risk_per_trade

    async def balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Muestra el balance actual"""
        try:
            # Obtener balance del exchange
            balance = self.trading_bot.get_balance()  # Necesitamos implementar este método
            message = "💰 Balance actual:\n\n"
            for asset, amount in balance.items():
                message += f"{asset}: {amount}\n"
            await update.callback_query.message.reply_text(message)
        except Exception as e:
            await update.callback_query.message.reply_text(f"Error al obtener balance: {str(e)}")

    async def execute_trade(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Ejecuta una operación de trading"""
        query = update.callback_query
        action = query.data  # 'buy' o 'sell'
        
        # Mostrar teclado de selección de activo
        keyboard = [
            [InlineKeyboardButton("BTC", callback_data=f'{action}_BTC'),
             InlineKeyboardButton("ETH", callback_data=f'{action}_ETH')],
            [InlineKeyboardButton("SOL", callback_data=f'{action}_SOL'),
             InlineKeyboardButton("MATIC", callback_data=f'{action}_MATIC')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            f"Selecciona el activo para {'comprar' if action == 'buy' else 'vender'}:",
            reply_markup=reply_markup
        )

    async def show_signals(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Muestra las señales actuales de trading"""
        try:
            df = self.trading_bot.load_trading_data("Hyperliquid_all_metics_01_24_2025.csv")
            signals = generate_trading_signals(df, "BTC")
            
            message = "🔍 Señales actuales:\n\n"
            for _, row in signals.iterrows():
                signal = row["Signal"]
                asset = row["Most Profitable Symbol"]
                message += f"{asset}: {signal} 📊\n"
            
            await update.callback_query.message.reply_text(message)
        except Exception as e:
            await update.callback_query.message.reply_text(f"Error al obtener señales: {str(e)}")

    def run(self):
        """Inicia el bot de Telegram"""
        application = Application.builder().token(TELEGRAM_TOKEN).build()
        
        # Registrar handlers
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CallbackQueryHandler(self.connect_wallet, pattern="^connect_wallet$"))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_wallet_input))
        application.add_handler(CallbackQueryHandler(self.balance, pattern="^balance$"))
        application.add_handler(CallbackQueryHandler(self.execute_trade, pattern="^(buy|sell)"))
        application.add_handler(CallbackQueryHandler(self.show_signals, pattern="^signals$"))
        application.add_handler(CallbackQueryHandler(self.auto_trading_menu, pattern="^auto_trading$"))
        application.add_handler(CallbackQueryHandler(self.toggle_auto_trading, pattern="^auto_trading_toggle$"))
        
        # Iniciar el bot
        application.run_polling()

if __name__ == "__main__":
    telegram_trader = TelegramTrader()
    telegram_trader.run() 