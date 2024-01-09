
from importlib import resources as impresources
from birthday_bot import resources

def read_file(filename):
    '''Read file from resources'''
    with impresources.open_text(resources, filename) as f:
        file = f.read()
    return file


def get_present_message():
    '''Read present message from resources/present_message.txt'''
    present_message = read_file('present_message.txt')
    return present_message

def get_rules():
    '''Read rules from resources/rules.txt
    use new line as separator'''
    rules = read_file('rules.txt').split('\n')
    rules_str = '\n**\t\t\t\t\tПравила вечиринки** \n\n'
    for rule in rules:
        rules_str = f"{rules_str}- {rule.strip()}\n"
    return rules_str


def get_greeting_message():
    '''Read greeting message from resources/greeting_message.txt'''
    greeting_message = read_file('greeting_message.txt')
    greeting_message = f"""{greeting_message}\n
    {get_address_msg()}
    {read_file('activity.txt')}
    {get_rules()}
    {get_present_message()}"""
    return greeting_message

def get_address_msg():
    '''Read address from resources/address.txt'''
    address = read_file('address.txt')
    return address