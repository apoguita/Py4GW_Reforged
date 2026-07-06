import PySystem
var = 0

#this is the absolute minimum you can do to make a script run.
def main():
    global var
    var += 1
    PySystem.Console.Log("Barebones Module", f"Cycles Evaluated: {var}",PySystem.Console.MessageType.Notice)

if __name__ == "__main__":
    main()
