from Py4GWCoreLib import *
from Py4GWCoreLib.FrameTree import Frame, FrameId
module_name = "Return to Outpost"

class config:
    def __init__(self):
        self.is_map_loading = False
        self.is_map_ready = False
        self.is_party_loaded = False
        self.material_salvaging_window = False
        self.frame_id = 0
        self.dialog_accepted = False
        self.map_valid = False
        self.frame_label = "Salvage Materials Dialog"
        
        self.game_throttle_time = 100
        self.game_throttle_timer = Timer()
        self.game_throttle_timer.Start()

widget_config = config()



def configure():
    pass

def main():
    global widget_config
    
    if Map.IsMapLoading():
        widget_config.dialog_accepted = False
        widget_config.material_salvaging_window = False
        return
    
    if not (Map.IsMapReady() and Party.IsPartyLoaded()):
        return
    
    
    if widget_config.game_throttle_timer.HasElapsed(widget_config.game_throttle_time):
        widget_config.game_throttle_timer.Reset()
        yes_button = Frame(FrameId.ScreenFrame.C6.SalvageMaterialsDialog.YesButton)

        if not yes_button.exists:
            widget_config.dialog_accepted = False
            widget_config.material_salvaging_window = False
            return
        
        if widget_config.dialog_accepted:
            return
        
        ActionQueueManager().AddAction("ACTION", yes_button.click)
        widget_config.dialog_accepted = True
        

if __name__ == "__main__":
    main()
