import pathlib

content = open('C:/Users/ddpat/Desktop/DATADOG_Hackathon/Datadog-Hack/code/backend/tests/_test_template.txt', encoding='utf-8').read()
with open('C:/Users/ddpat/Desktop/DATADOG_Hackathon/Datadog-Hack/code/backend/tests/test_api_endpoints.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Written OK')
