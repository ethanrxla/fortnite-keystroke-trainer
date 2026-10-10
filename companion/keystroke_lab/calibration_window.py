"""Interactive per-player key calibration; no synthetic game input."""
import queue
from pathlib import Path
from . import actions, drills, keyboard_overlay
from .bind_profiles import ProfileStore

def run(path=None):
    import tkinter as tk
    from pynput import keyboard, mouse
    path=Path(path or drills.BINDS_FILE)
    store=ProfileStore(path,confirm_sprint=path==drills.BINDS_FILE)
    todo=actions.actions_in(None);index=0;pending=[];events=queue.Queue();alternate=False
    root=tk.Tk();root.title('Training Lab - Key calibration');root.geometry('660x530');root.configure(bg='#101724')
    root.attributes('-topmost',True)
    rect=keyboard_overlay.game_rect()
    if rect:
        l,t,r,b=rect;root.geometry(f'660x620+{l+max(0,(r-l-660)//2)}+{t+max(0,(b-t-620)//2)}')
    from .player_profiles import PlayerProfiles
    archive=PlayerProfiles(path.with_name('player-profiles.json'))
    player_name=tk.StringVar(value=next((n for n in archive.names() if archive.load(n).profile_id==store.snapshot.profile_id),'Local player'))
    player_row=tk.Frame(root,bg='#101724');player_row.pack(pady=(8,0))
    tk.Label(player_row,text='Player profile',bg='#101724',fg='white').pack(side='left')
    from tkinter import ttk
    choice=ttk.Combobox(player_row,textvariable=player_name,values=archive.names(),width=20);choice.pack(side='left',padx=6)
    def save_player():
        if not player_name.get().strip():return
        store.activate(archive.save(player_name.get(),store.snapshot))
        choice['values']=archive.names()
    def load_player():
        if player_name.get() not in archive.names():return
        store.activate(archive.load(player_name.get()));display()
    tk.Button(player_row,text='Load',command=load_player).pack(side='left',padx=4)
    tk.Button(player_row,text='Save player',command=save_player).pack(side='left',padx=4)
    title=tk.Label(root,text='Your Fortnite controls',font=('Segoe UI',20,'bold'),fg='white',bg='#101724');title.pack(pady=(20,8))
    progress=tk.Label(root,font=('Segoe UI',10),fg='#8fa5be',bg='#101724');progress.pack()
    prompt=tk.Label(root,font=('Segoe UI',16,'bold'),fg='#65e8ae',bg='#101724',wraplength=610);prompt.pack(pady=18)
    value=tk.Label(root,font=('Segoe UI',13),fg='white',bg='#101724',wraplength=610);value.pack(pady=8)
    instructions=tk.Label(root,text='Press the key for this action. For mouse bindings, click the blank area\nor use a side button / wheel. Escape skips. Buttons below never count.',font=('Segoe UI',10),fg='#bdc8d8',bg='#101724');instructions.pack(pady=14)
    scale_row=tk.Frame(root,bg='#101724');scale_row.pack(pady=8)
    tk.Label(scale_row,text='Keyboard overlay size',bg='#101724',fg='white').pack(side='left')
    def change_scale(value):
        import json
        (Path(__file__).resolve().parents[1]/'overlay-settings.json').write_text(json.dumps({'scale':float(value)/100}))
    scale=tk.Scale(scale_row,from_=100,to=200,orient='horizontal',length=270,command=change_scale,bg='#101724',fg='white',highlightthickness=0)
    scale.set(150);scale.pack(side='left',padx=12)
    footer=tk.Frame(root,bg='#101724');footer.pack(side='bottom',pady=20)
    hit_area={'bounds':None}
    def display():
        nonlocal pending,alternate
        if index>=len(todo):
            prompt.config(text='Calibration saved');value.config(text='Your keyboard overlay uses the updated profile.');progress.config(text='Complete');save.config(state='disabled');add.config(state='disabled');skip.config(state='disabled');return
        action=todo[index];b=next((b for b in store.snapshot.bindings if b.action==action),None)
        progress.config(text=f'{index+1} / {len(todo)}   ·   {actions.CATEGORY_OF.get(action,"control")}')
        prompt.config(text=actions.PROMPTS.get(action,action).capitalize())
        value.config(text='Press a key…' if not pending else 'Selected: '+ ' / '.join(pending))
        if b and not pending:value.config(text='Current: '+' / '.join(b.keys)+ ('  (confirmed)' if b.verified else '  (unverified)'))
    def capture(key):
        nonlocal pending,alternate,index
        if index>=len(todo):return
        if key=='esc':advance(False);return
        if not alternate:pending=[key]
        elif key not in pending:pending.append(key)
        alternate=False;display()
    def advance(save_it):
        nonlocal pending,index,alternate
        if index>=len(todo):return
        action=todo[index]
        if save_it:
            if not pending:return
            store.update(action,pending,actions.CATEGORY_OF.get(action,'any'),verified=True)
            save_player()
        index+=1;pending=[];alternate=False;display()
    def add_alternate():
        nonlocal alternate
        if pending:alternate=True;value.config(text='Press an alternate key for this action…')
    save=tk.Button(footer,text='Save & next',command=lambda:advance(True),font=('Segoe UI',11));save.pack(side='left',padx=5)
    add=tk.Button(footer,text='Add alternate',command=add_alternate,font=('Segoe UI',11));add.pack(side='left',padx=5)
    skip=tk.Button(footer,text='Skip',command=lambda:advance(False),font=('Segoe UI',11));skip.pack(side='left',padx=5)
    finish=tk.Button(footer,text='Finish later',command=root.destroy,font=('Segoe UI',11));finish.pack(side='left',padx=5)
    def focused():return 'Training Lab - Key calibration' in keyboard_overlay.foreground_title()
    def key_pressed(k):
        if focused():events.put(keyboard_overlay.normal(getattr(k,'char',None) or getattr(k,'name',k)))
    def click(x,y,b,pressed):
        if not pressed or not focused():return
        bounds=hit_area['bounds']
        if bounds and bounds[0]<=x<=bounds[2] and bounds[1]<=y<=bounds[3]:return
        events.put('mouse_'+b.name)
    kl=keyboard.Listener(on_press=key_pressed);ml=mouse.Listener(on_click=click,on_scroll=lambda x,y,dx,dy:events.put('wheel_up' if dy>0 else 'wheel_down') if focused() else None)
    kl.start();ml.start()
    def poll():
        hit_area['bounds']=(footer.winfo_rootx()-8,footer.winfo_rooty()-8,footer.winfo_rootx()+footer.winfo_width()+8,footer.winfo_rooty()+footer.winfo_height()+8)
        while not events.empty():capture(events.get_nowait())
        root.after(8,poll)
    display();root.after(40,poll)
    try:root.mainloop()
    finally:kl.stop();ml.stop()

if __name__=='__main__':
    import sys
    run(sys.argv[1] if len(sys.argv)>1 else None)
