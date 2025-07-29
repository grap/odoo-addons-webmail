# Code from https://raw.githubusercontent.com/polygphys-emilejetzer/outils/889c5b20dec453bba295444f34d989fece0fbc0f/reseau/courriel.py

import re


def modified_unbase64(s: str) -> str:
    s_utf7 = "+" + s.replace(",", "/") + "-"
    return s_utf7.encode().decode("utf-7")


def decode_imap4_utf7(s: str) -> str:
    r = list()
    if s.find("&-") != -1:
        s = s.split("&-")
        i = len(s)
        for subs in s:
            i -= 1
            r.append(decode_imap4_utf7(subs))
            if i != 0:
                r.append("&")
    else:
        regex = re.compile(r"[&]\S+?[-]")
        sym = re.split(regex, s)
        if len(regex.findall(s)) > 1:
            i = 0
            r.append(sym[i])
            for subs in regex.findall(s):
                r.append(decode_imap4_utf7(subs))
                i += 1
                r.append(sym[i])
        elif len(regex.findall(s)) == 1:
            r.append(sym[0])
            r.append(modified_unbase64(regex.findall(s)[0][1:-1]))
            r.append(sym[1])
        else:
            r.append(s)
    return "".join(r)


def clean_subject(subject):
    return re.sub(r"(((RE)|(Re)|(Fwd)|(TR)): )+", "", subject)


def client_select(client, folder_name):
    print("client_select", folder_name)
    status, select_code = client.select(folder_name)
    return status, select_code