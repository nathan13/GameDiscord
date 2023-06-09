import discord
from discord.ext import commands
import configparser
import asyncio

# Define a bot with all the intents
bot = commands.Bot(intents=discord.Intents.all())

CONFIG_PATH = 'config.ini'

# Define a class to manage the bot's settings
class ConfigManager:
    def __init__(self, config_path=CONFIG_PATH):
        self.config = configparser.ConfigParser()
        self.config.read(config_path)

    # Method to get the token stored in the configuration file
    def get_token(self):
        return self.config.get('DEFAULT', 'token')

    # Method to get the channel ID stored in the configuration file
    def get_channel_id(self):
        return int(self.config.get('DEFAULT', 'channel_id'))

# Read and save the token and default channel ID from the configuration file using the ConfigManager
config_manager = ConfigManager()
token = config_manager.get_token()
default_channel_id = config_manager.get_channel_id()

#- - - - | MyView Class | - - - -
class MyView(discord.ui.View):
    def __init__(self,msg):
        super().__init__()
        #original message
        self.msg = msg
        
        #set the timeout to delete responded messsages
        self.delete_message_timeout = 10

        # Work Counter presets
        self.work_counter_timeout = 5
        self.work_counter_price = self.work_counter_timeout * 5
        self.work_amount_count = 0
        self.update_work_counter = 0
        self.work_counter_task = None

        # Hunting Loop presets
        self.monster_found = None
        self.hunting_loop_task = None

        # Saves references to the buttons
        self.my_work_button = self.children[0]
        self.my_hunting_button = self.children[1]
        self.my_cancel_button = self.children[2]
        
        #create the default monster (rat, boar, goblin)
        self.monster =  HuntingManager.default_monster()
        
        #Create a Player Instance
        self.player = Player(self.msg.author.id,self.msg.author.nick)
        
        #create embeds (hunt and work screen)
        self.embed_manager = EmbedManager(self)
        self.embed_manager.create_embeds()

        #Create instances for manager classes
        self.button_manager = ButtonManager(self)
        self.hunting_manager = HuntingManager(self)
        self.work_manager = Workstation(self)

        
    #check if the user of the interaction is the same one who sent the message
    def check_interaction(interaction,msg):
        return int(interaction.user.id) != int(msg.author.id)
    
    #delete responded message on timeout 
    async def delete_responded_message(self):
        await asyncio.sleep(self.delete_message_timeout)
        await self.msg.delete()


    

    @discord.ui.button(label='Work')
    async def work_button(self, button: discord.ui.Button, interaction: discord.Interaction):
       if MyView.check_interaction(interaction, self.msg):
           return
       #check whether it is a start work or a stop work and direct the right way
       if self.my_work_button.label == "Work":
            await self.button_manager.start_work(interaction)
       else:
            await self.button_manager.stop_work(interaction)
    
    @discord.ui.button(label='Start Hunting', style=discord.ButtonStyle.blurple)
    async def start_hunting_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        if MyView.check_interaction(interaction, self.msg):
           return
        
        #check whether it is a start hunting or a stop hunting and direct the right way
        if self.my_hunting_button.label == "Start Hunting":
            await self.button_manager.start_hunting(interaction)
        else:
            await self.button_manager.stop_hunting(interaction)

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.red)
    async def cancel_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        if MyView.check_interaction(interaction, self.msg):
           return
        await self.button_manager.start_cancel(interaction)

# - - - - | EmbedManager Class | - - - -
class EmbedManager():
    def __init__(self,view):
        self.view = view
        #player reference
        self.player = self.view.player
    
    def create_embeds(self):
        """ Creates the "Work Embed" Screen and the "Hunt Embed" Screen generated by the respective buttons

        Returns:

        Created Embeds
        """
        #"Work Embed"
        self.embed_work = discord.Embed(title = "Workstation", description = f"--- Work to buy Counter and recover your Health ---\n-> {self.view.work_counter_timeout} Counter costs {self.view.work_counter_timeout * 5} silvers\n-> {self.view.work_counter_timeout} Counter recover {self.view.work_counter_timeout * 5} health")
        self.embed_work.add_field(name="Counter", value =str(self.view.update_work_counter), inline=True)
        self.embed_work.add_field(name="Your Silver", value =f"{self.player.silver}", inline=True)
        self.embed_work.add_field(name="Your Health", value =f"{self.player.health}/{self.player.max_health}", inline=True)

        #"Hunt Embed"
        self.embed_hunt = discord.Embed(title = "Game Information", description = "Kill monsters to farm silver and experience")
        self.embed_hunt.add_field(name='Player', value=f"Name: {self.player.name}\nLevel: {self.player.level}\nExperience: {self.player.experience}\nSilver: {self.player.silver}\nHealth: {self.player.health}/{self.player.max_health}\nMonsters Defeated: 0", inline=True)
        self.embed_hunt.add_field(name="", value ="")


# - - - - | ButtonManager Class | - - - -
class ButtonManager:
    def __init__(self,view):
        self.view = view
        

        #Button References
        self.cancel_button = self.view.my_cancel_button
        self.work_button = self.view.my_work_button
        self.hunt_button = self.view.my_hunting_button

        #Embed references
        self.embed_work = self.view.embed_manager.embed_work
        self.embed_hunt = self.view.embed_manager.embed_hunt

        #Another references
        self.update_work_counter = self.view.update_work_counter
        self.player = self.view.player
        

    def button_disabled(self,status:bool,button_name1:str,button_name2:str = None,button_name3:str = None):
        """Update the View disabling/enabling buttons sent by "button_name".

        Keyword arguments:

        status = True to enable|False to disable

        button_name1 =  "Work","Cancel","Hunt"

        Returns:

        Buttons Disabled/Enabled
        """
        buttons = []
        buttons.extend([button_name1,button_name2,button_name3])  

        #Check the button name and find the corresponding button
        for button in buttons:
            if button == "work":
                self.work_button.disabled = status
            elif button == "cancel":
                self.cancel_button.disabled = status
            elif button == "hunt":
                self.hunt_button.disabled = status

    async def start_work(self,interaction): 
        """Sends the "Work Embed" to the screen and checks the player's 
           conditions to continue or not with the action".
        """
        self.embed_work.title = "Workstation"
        self.view.update_work_counter = 0
        self.view.work_manager.update_work_info("","")
        await interaction.edit(embed = self.embed_work)
        if self.view.player.health  < self.view.player.max_health:
            if self.view.player.silver >= 25:
                self.view.work_amount_count = 0 
                self.view.my_work_button.label = "Stop Work"
                self.button_disabled(True,"hunt","cancel") 
                self.embed_work.title = "Workstation (Working.)"
                await interaction.edit(embed = self.embed_work, view = self.view),

                #starts the work_counter ansycio task
                self.view.work_counter_task = asyncio.create_task(self.view.work_manager.work_counter(interaction))

            else:
                self.embed_work.title = "Workstation (Not enough silver to do it)"
                await interaction.edit(embed = self.embed_work)
        else:
           self.embed_work.title = "Workstation (You are already at maximum health)"
           await interaction.edit(embed = self.embed_work)

    async def start_hunting(self,interaction):
        """Sends the "Hunt Embed" to the screen and starts hunting.
        """
        self.view.my_hunting_button.label = "Stop Hunting"  
        self.button_disabled(True,"work","cancel")  
        await interaction.edit(view = self.view, embed = self.embed_hunt)

        #start hunting loop asyncio task
        self.view.hunting_loop_task = asyncio.create_task(self.view.hunting_manager.hunting_loop(interaction))

    async def start_cancel(self, interaction):
        """Makes the bot unusable by disabling the button and sending a farewell message.
        """
        self.button_disabled(True,"work","cancel","hunt") 
        await interaction.edit(embed = self.embed_hunt ,view = self.view)
        await interaction.message.reply('Goodbye!')
    
    async def stop_work(self,interaction):
        """Cancels work counter task, resets screen and buttons to initial setting and update Embeds informations.
        """
        self.view.work_counter_task.cancel()
        self.view.my_work_button.label = "Work"
        self.button_disabled(False,"cancel","hunt")
        self.view.hunting_manager.update_player_info()
        self.view.work_manager.update_work_info(f"(-{self.view.work_amount_count})",f"(+{self.view.work_amount_count})")
        await interaction.edit(embed = self.embed_work, view = self.view)

    async def stop_hunting(self,interaction):
        """Cancels hunting counter task, resets screen and buttons to initial setting and update Embeds informations.
        """
        self.view.hunting_loop_task.cancel()
        self.view.my_hunting_button.label = "Start Hunting"
        self.button_disabled(False,"work","cancel") 
        self.view.hunting_manager.update_monster_info("")
        self.view.work_manager.update_work_info("","")
        await interaction.edit(embed = self.embed_hunt, view = self.view)

        #check monster existence and reset its max_health
        if self.view.monster_found != None:
            self.view.monster_found.health = self.view.monster_found.max_health
            self.view.monster_found = None

        await interaction.edit(embed = self.embed_hunt, view = self.view)

class Workstation:
    def __init__(self,view):
        self.view = view
        
        #Embeds references
        self.embed_work = self.view.embed_manager.embed_work
        self.embed_hunt = self.view.embed_manager.embed_hunt
        
    async def work_counter(self,interaction):
        """
            Check the player's silver and health to continue or not recovering health spent on silver
        """
        while True:
            #check if (player silver - counter price) >= 0
            if (self.view.player.silver - self.view.work_counter_price) >= 0:

                #check if (player health + counter price) <= player max health
                if (self.view.player.health + self.view.work_counter_price) < self.view.player.max_health:
                    await self.work_timer(interaction)

                    #updates variables with the new values
                    self.view.player.health += self.view.work_counter_price
                    self.view.player.silver -= self.view.work_counter_price
                    self.view.update_work_counter += self.view.work_counter_timeout
                    self.view.work_amount_count += self.view.work_counter_price

                    self.update_work_info(f"(-{self.view.work_amount_count})",f"(+{self.view.work_amount_count})")
                    await interaction.edit(embed = self.embed_work)
                    
                else: 
                    await self.work_timer(interaction)
                    
                    #updates variables with the new values
                    self.view.player.silver -= self.view.work_counter_price
                    self.view.update_work_counter += self.view.work_counter_timeout
                    self.view.work_amount_count += self.view.work_counter_price
                    self.view.player.health = self.view.player.max_health

                    self.embed_work.title = "Workstation (You have reached maximum health)"
                    self.update_work_info(f"(-{self.view.work_amount_count})",f"(+{self.view.work_amount_count})")
                    await interaction.edit(embed = self.embed_work)
                    await self.view.button_manager.stop_work(interaction)
            else:
                self.embed_work.title = "Workstation (Not enough silver to continue)"
                await interaction.edit(embed = self.embed_work)
                await self.view.button_manager.stop_work(interaction)

                
    
    def update_work_info(self,silver_amount,health_amount):
        """ Update the "Work Embed" with the new values

        Keyword arguments:

        silver_amount = amount of silver used in work count

        health_amount = amount of health used in job count

        Returns:

        "Work Embed" updated
        """
        self.embed_work.set_field_at(index=0, name= "Counter", value =f"{self.view.update_work_counter}")
        self.embed_work.set_field_at(index=1, name= "Your Silver", value =f"{self.view.player.silver}{silver_amount}")
        self.embed_work.set_field_at(index=2, name= "Your Health", value =f"{self.view.player.health}/{self.view.player.max_health}{health_amount}")
        

    async def work_timer(self, interaction):
        """ Simulates a waiting time with messages interspersed between the time determined by the Work Timeout

        Returns:

        "Working." "Working.." "Working..."
        """


        messages = []
        messages.extend(["Workstation (Working.)","Workstation (Working..)","Workstation (Working...)"])

        for message in messages:
            self.embed_work.title = message
            await interaction.edit(embed = self.embed_work)
            await asyncio.sleep(self.view.work_counter_timeout / 3)

class HuntingManager:
    def __init__(self,view):
        self.monsters_defeated = 0
        self.view = view
        self.player = self.view.player
        
        #Embeds references
        self.embed_work = self.view.embed_manager.embed_work
        self.embed_hunt = self.view.embed_manager.embed_hunt

    
    async def hunt_timer(self, interaction):
        """ Simulates a waiting time with messages interspersed between 2 seconds
        
        Returns:

        "Hunting." "Hunting.." "Hunting..."
        """
        messages = []
        messages.extend(["Hunting.","Hunting..","Hunting..."])

        for message in messages:
            self.update_monster_info(message)
            await interaction.edit(embed = self.embed_hunt)
            await asyncio.sleep(0.7)




    def default_monster():
        """Create the default monsters in the Monster Class
        """
        Monster('Rat',1)
        Monster('Boar',2)
        Monster('Goblin',3)
    
    def update_player_info(self):
        """ Update the "Hunt Embed" with informations stored in Player Class
        """
        self.embed_hunt.set_field_at(index=0, name='Player', value=f"Name: {self.player.name}\nLevel: {self.player.level}\nExperience: {self.player.experience}\nSilver: {self.player.silver}\nHealth: {self.player.health}/{self.player.max_health}\nMonsters Defeated: {self.monsters_defeated}", inline=True)
    
    def update_monster_info(self,name = None):
        """ Update the "Hunt Embed" with informations stored in Monster Class
        """
        if name == None:
            self.embed_hunt.set_field_at(index=1, name="Monster found", value = f"Name: {self.view.monster_found.name}\nLevel: {self.view.monster_found.level}\nHealth: {self.view.monster_found.health}/{self.view.monster_found.max_health}")
        elif name == "":
            self.embed_hunt.set_field_at(index=1, name= name, value = "")
        else:
            self.embed_hunt.set_field_at(index=1, name= name, value = "No monsters currently")


    async def hunting_loop(self,interaction):
        """
            Check the player's silver and health to continue or not recovering health spent on silver
        """
        while True:
            if self.view.monster_found == None:
                await self.hunt_timer(interaction)
                for monster in Monster.instances:
                    if monster.level == self.view.player.level:
                        self.view.monster_found = monster
                        self.update_monster_info()                
                        await interaction.edit(embed = self.embed_hunt)
                        await asyncio.sleep(1)
                        await self.battle(interaction) 
            else:
                await asyncio.sleep(1)
                await self.battle(interaction) 
                
               
    

    async def battle(self,interaction):
        """
            Control the battle by checking Player and monster informations
        """
        #hit the monster
        self.view.monster_found.health -= 5*self.view.player.level

        #if monster died
        if self.view.monster_found.health <= 0:
             self.view.player.experience += 10
             self.view.monster_found.health = self.view.monster_found.max_health
             self.view.player.silver += 5 * self.view.monster_found.level
             self.monsters_defeated += 1
            
            #if player experience is at maximum
             if self.view.player.experience >= 100:
                 self.view.player.level += 1
                 self.view.player.experience -= 100
                
                #if player level is at maximum
                 if self.view.player.level == 4:                  
                    self.view.button_manager.button_disabled(True,"work","cancel","hunt") 
                    self.view.my_hunting_button.label = "Start Hunting"
                    self.update_monster_info("")
                    self.update_player_info()
                    self.view.monster_found = None
                    await interaction.edit(embed = self.embed_hunt, view = self.view)
                    await interaction.message.reply("You won!")
                    self.view.hunting_loop_task.cancel()  
                    
             self.update_player_info()
             self.view.monster_found = None        
             
        else:

            #hit the player
            self.view.player.health -= 2*self.view.monster_found.level

            #if player died
            if self.view.player.health <= 0:
                self.view.player.health = self.view.player.max_health
                self.view.button_manager.button_disabled(False,"work","cancel","hunt") 
                self.view.my_hunting_button.label = "Start Hunting"
                self.update_monster_info("")
                self.update_player_info()
                self.view.monster_found = None
                await interaction.edit(embed = self.embed_hunt, view = self.view)
                await interaction.message.reply("You have died!")
                self.view.hunting_loop_task.cancel()         
            else:
                self.update_player_info()
                self.update_monster_info()

        await interaction.edit(embed = self.embed_hunt)

class Player:
    def __init__(self,discord_id,user_name):
        self.discord_id = discord_id
        self.name = user_name
        self.level = 1
        self.experience = 0
        self.silver = 0
        self.max_health = 250
        self.health = 250

class Monster:
    instances = []
    def __init__(self,monster_name,monster_level):
        self.name = monster_name
        self.level = monster_level
        self.max_health = 20 * self.level
        self.health = self.max_health
        #add the instance to monster_instances
        Monster.instances.append(self)
    
# Define an event for when a message is sent in a specific channel with the content "!bot"
async def on_message(msg):
    if msg.channel.id == default_channel_id and msg.content == "!bot":
        view = MyView(msg)
        # Reply to the message with a mention to the author and a custom view
        await msg.reply(msg.author.mention, view=view, embed = view.embed_manager.embed_hunt)
        await view.delete_responded_message()

bot.add_listener(on_message)

# Run the bot with the token from the configuration file
bot.run(token)