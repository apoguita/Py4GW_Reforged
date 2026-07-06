from Py4GWCoreLib import *

module_name = "Script Template"

# Example of additional utility function
def PerformTask():
    global module_name
    try:
        # Example task logic
        # Replace with actual logic
        return "Task completed"
    except Exception as e:
        # Log and re-raise exception to ensure the main script can handle it
        PySystem.Console.Log(module_name, f"Error in PerformTask: {str(e)}", PySystem.Console.MessageType.Error)
        raise

# main function must exist in every script and is the entry point for your script's execution.
def main():
    global module_name
    try:
        # Place your main logic here
        # Example:
        # result = PerformTask()
        # PySystem.Console.Log("YourModule", f"Task result: {result}", PySystem.Console.MessageType.Info)
        
        pass  # Replace with your actual code

    # Handle specific exceptions to provide detailed error messages
    except ImportError as e:
        PySystem.Console.Log(module_name, f"ImportError encountered: {str(e)}", PySystem.Console.MessageType.Error)
        PySystem.Console.Log(module_name, f"Stack trace: {traceback.format_exc()}", PySystem.Console.MessageType.Error)
    except ValueError as e:
        PySystem.Console.Log(module_name, f"ValueError encountered: {str(e)}", PySystem.Console.MessageType.Error)
        PySystem.Console.Log(module_name, f"Stack trace: {traceback.format_exc()}", PySystem.Console.MessageType.Error)
    except TypeError as e:
        PySystem.Console.Log(module_name, f"TypeError encountered: {str(e)}", PySystem.Console.MessageType.Error)
        PySystem.Console.Log(module_name, f"Stack trace: {traceback.format_exc()}", PySystem.Console.MessageType.Error)
    except Exception as e:
        # Catch-all for any other unexpected exceptions
        PySystem.Console.Log(module_name, f"Unexpected error encountered: {str(e)}", PySystem.Console.MessageType.Error)
        PySystem.Console.Log(module_name, f"Stack trace: {traceback.format_exc()}", PySystem.Console.MessageType.Error)
    finally:
        pass

# This ensures that Main() is called when the script is executed directly.
if __name__ == "__main__":
    main()
