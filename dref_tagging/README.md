To run this app

Copy the file DREF_docBERT.pt into the folder tagging_app/config

From command line cd into folder tagging_app

run commands

```
docker build -t tagging2 .  
docker run -p 8000:8000 tagging2
```

On IFRC Azure infrastructure the app is available at: 
https://dreftagging.azurewebsites.net/docs
