import yaml

with open('E:/funny_project/nameforge/config/styles.yaml', 'r', encoding='utf-8') as f:
    data = yaml.safe_load(f)

print("Top level keys:", list(data.keys()))
print("\nstyles keys:", list(data.get('styles', {}).keys()))

acg = data.get('styles', {}).get('二次元', {})
print("\n二次元 keys:", list(acg.keys()))
print("\ntags config:", acg.get('tags', 'NOT FOUND'))
