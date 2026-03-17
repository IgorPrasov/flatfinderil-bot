import browser_cookie3

try:
    cookies = browser_cookie3.chrome(domain_name='.facebook.com')
    with open('cookies.txt', 'w') as f:
        f.write("# Netscape HTTP Cookie File\n")
        for c in cookies:
            f.write(f".facebook.com\tTRUE\t/\t{'TRUE' if c.secure else 'FALSE'}\t{int(c.expires or 0)}\t{c.name}\t{c.value}\n")
    print("✅ cookies.txt создан успешно!")
except Exception as e:
    print(f"❌ Ошибка: {e}")
