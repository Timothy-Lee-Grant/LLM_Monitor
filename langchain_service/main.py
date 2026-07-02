
#from lang import invoke_langchain
#import lang_practice
#from lang_practice import TestingMethod, TestRagSystem, TestToolUseSystem, TestInit
#from swagger_ui import api_doc #TODO: implement this later

from "./app/api/FlaskServer" import IntializeFlaskEndpoints





if __name__ == "__main__":
    app = IntializeFlaskEndpoints()
    app.run(host="0.0.0.0", port=5000, debug=True)