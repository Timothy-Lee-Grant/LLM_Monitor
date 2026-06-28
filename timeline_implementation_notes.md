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