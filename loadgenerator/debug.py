# connect with:
# $ rlwrap nc -v 127.0.0.1 4444
def d():
    from remote_pdb import RemotePdb
    RemotePdb('127.0.0.1', 4444).set_trace()

def preview_html(html):
    from tempfile import NamedTemporaryFile
    f = NamedTemporaryFile(delete=False, suffix=".html")
    f.write(html)
    f.close()
    import webbrowser
    webbrowser.open_new_tab("file://" + f.name)
