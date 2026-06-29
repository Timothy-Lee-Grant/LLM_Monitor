# June 26, 2026:
## Stateful Langchain
I will implement langchain at first to be stateful. This will mean that I will just store the user information and chat history. I will not keep user information in an external database and grab it per request. I will also at first assume that user requesting is always the same user. 

Later implementations I will need to dynaically load that user's chat history based on their user id. This will solve both the stateless/stateful issue, and also allow for multi-user sessions on the server. But for simplicity sake, right now I will just make these two assumptions to get the system up and running and tested.

# June 27, 2026
## Change Internal API Requests To gRPC
I need to look into the way that I want to send communications between different microservices on my system. I might want to switch from HTTP (current method), to gRPC.

## Implement Image Upload
```
POST /api/images HTTP/1.1
Content-Type: multipart/form-data; boundary=----WebKitFormBoundaryXYZ

------WebKitFormBoundaryXYZ
Content-Disposition: form-data; name="userId"

42
------WebKitFormBoundaryXYZ
Content-Disposition: form-data; name="avatar"; filename="me.jpg"
Content-Type: image/jpeg

[RAW BINARY BYTES / STREAM DATA GOES HERE]
------WebKitFormBoundaryXYZ--
```


```
[HttpPost("upload")]
public async Task<IActionResult> UploadImage(IFormFile avatar)
{
    // .NET has reconstructed the file metadata and binary data into the 'avatar' object
    var fileName = avatar.FileName; // "me.jpg"
    
    // Open the stream to read the reconstructed raw bytes:
    using var stream = avatar.OpenReadStream();
    
    // You can now save it to disk, cloud storage, or process it
    await avatar.CopyToAsync(new FileStream("/uploads/me.jpg", FileMode.Create));

    return Ok();
}
```

## Implement vector Database
As of right now, I don't have any vector database, so I need to be able to implement this within docker ecosystem. I will then need to make it such that I can load the data on start up if it does not exist already, and if it does exist, I will leave it. But this brings up an interesting questin of who is actually the one doing this? Is it the docker container that will be running pgvector, or is it one of the services in my application?

## Implement pop up window on start up
Eventually it would be cool to have multiple start up scripts. One script just does default parameters, another script does all testing parameters, ect. But then the 'real' one is a script that the user be able to get a pop up window. This pop up window will allow the user to configure the system by putting in their local model path location (so they would point physically to the path on their local set up), or they could point to the file contianing their api keys. (and this pop up will also let them configure all of the other settings which I will implement.)

This would be cool because it would force me to create a pop up that the user can navigate, I will need to make it work for multiple operating systems (windows, mac, linux), and I will need to be able to navigate (so interact with the OS and the file system on their local machine).

In addition I will also need to learn how to securely store those api keys.

# June 28, 2026

## Other Ideas to Integrate

Langgraph, Xunit testing, AI as a judge testing, LangSmith.

## Thoughts on Scalability

If I have my langchain docker contianer, and it is running flask. Then flask invokes a method to do the langchain processing. As of now I am assuming that we will have one person sending messages and it will be the same person. But once we want to change the systme to allow for multi-users, this architecture seems to force us into a bad spot.

If the objects are created new each time when the function is invoked, that means that we are creating so many new object over and over. It also means that as we get multiple requests at the same time, that it will ___
But then I was thinking about if we could do pooling of resources, but I don't know if this will mix up the data in between calls.

I need to start considering how I will allocate resources such that I can transition into a muti-user system in the future, once I get to the point in this project that I am ready to implement that.

## Improve Speed
I remember that I can load a model into memory and keep it there (assuming that your hardware has enough space in RAM to be able to keep that ollama model in there), this dramatically reduces the time needed each chat to get a response back.