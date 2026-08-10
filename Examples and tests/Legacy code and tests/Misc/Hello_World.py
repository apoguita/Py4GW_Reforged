# Necessary Imports
import Py4GW        #Miscelanious functions and classes
import ImGui_Py     #ImGui wrapper
import traceback    #traceback to log stack traces
# End Necessary Imports

module_name = "Hello World!"

# Example of additional utility function
def DrawWindow():
    global module_name
    try:
        if ImGui_Py.begin(module_name):
        
            ImGui_Py.text("Hello World!")
            ImGui_Py.separator()
            
            if ImGui_Py.button("Click Me!"):
                    PySystem.Console.Log(module_name, "Yay!", PySystem.Console.MessageType.Success)
                    
            ImGui_Py.end()
    except Exception as e:
        # Log and re-raise exception to ensure the main script can handle it
        PySystem.Console.Log(module_name, f"Error in DrawWindow: {str(e)}", PySystem.Console.MessageType.Error)
        raise

# main function must exist in every script and is the entry point for your script's execution.
def main():
    global module_name
    try:
        DrawWindow()

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
        # Optional: Code that will run whether an exception occurred or not
        #PySystem.Console.Log(module_name, "Execution of Main() completed", PySystem.Console.MessageType.Info)
        # Place any cleanup tasks here
        pass

# This ensures that Main() is called when the script is executed directly.
if __name__ == "__main__":
    main()

