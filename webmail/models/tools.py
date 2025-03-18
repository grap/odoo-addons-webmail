# Code from https://raw.githubusercontent.com/polygphys-emilejetzer/outils/889c5b20dec453bba295444f34d989fece0fbc0f/reseau/courriel.py

import re


def modified_base64(s: str) -> str:
    s_utf7 = s.encode("utf-7")  #
    aaa = s_utf7[1:-1].decode().replace("/", ",")  # rfc2060
    return aaa


def modified_unbase64(s: str) -> str:
    s_utf7 = "+" + s.replace(",", "/") + "-"
    return s_utf7.encode().decode("utf-7")


def encode_imap4_utf7(s: str, errors=None) -> tuple[str, int]:
    r = list()
    _in = list()
    for c in s:
        if ord(c) in range(0x20, 0x25) or ord(c) in range(0x27, 0x7E):
            if _in:
                r.extend(["&", modified_base64("".join(_in)), "-"])
                del _in[:]
            r.append(str(c))
        elif ord(c) == 0x26:
            if _in:
                r.extend(["&", modified_base64("".join(_in)), "-"])
                del _in[:]
            r.append("&-")
        else:
            _in.append(c)
    if _in:
        r.extend(["&", modified_base64("".join(_in)), "-"])
    return "".join(r), len(s)


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
