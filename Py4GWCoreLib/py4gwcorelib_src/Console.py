import PySystem

@staticmethod
def ConsoleLog(sender, message, message_type:int=0 , log: bool = True):
    """Logs a message with an optional message type."""
    if log:
        if message_type == 0:
            PySystem.Console.Log(sender, message, PySystem.Console.MessageType.Info)
        elif message_type == 1:
            PySystem.Console.Log(sender, message, PySystem.Console.MessageType.Warning)
        elif message_type == 2:
            PySystem.Console.Log(sender, message, PySystem.Console.MessageType.Error)
        elif message_type == 3:
            PySystem.Console.Log(sender, message, PySystem.Console.MessageType.Debug)
        elif message_type == 4:
            PySystem.Console.Log(sender, message, PySystem.Console.MessageType.Success)
        elif message_type == 5:
            PySystem.Console.Log(sender, message, PySystem.Console.MessageType.Performance)
        elif message_type == 6:
            PySystem.Console.Log(sender, message, PySystem.Console.MessageType.Notice)
        else:
            PySystem.Console.Log(sender, message, PySystem.Console.MessageType.Info)

Console = PySystem.Console