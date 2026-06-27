using Microsoft.AspNetCore.Mvc;
using System.Net;
using System.Threading.Tasks;

namespace LLM_MONITOR.server.controllers;

[ApiController]
[Route("/api/[controller]")]
public class TestController : ControllerBase
{
    [HttpGet]
    public async Task<IActionResult> MyTestGetEndpoint()
    {
        return Ok(new {Message="Hello from my test endpoint :D "});
    }

    [HttpPost]
    public async Task<IActionResult> MyTestPostEndpoint([FromBody] String requestData)
    {
        await Task.Delay(10);
        return Ok(new {status = "Received", data = requestData});
    }
}

/*
[ApiController]
[Route("/api/[controller]")]
public class LlmController : ControllerBase
{
    private IHttpContextFactory _context;
    public LlmController(IHttpContextFactory context)
    {
        _context = context;
    }

    // Creating a test example DTO object that I can play around with for serialization and deserialization
    public class Dto
    {
        public String? Name {get; set;}
        public int Age {get; set;}
    }

    public void testSerialization()
    {
        // NOTE: here was my first attempt at trying to do the JSON serialization/deserialization
        // Obviously I still have a lot of conceptual understanding gaps and I need to practice and improve this to be more fluent.
        
        // String _myString = "{\"Name\":\"Timothy\",\"Age\":20}";
        // Dto myObject = JsonSerializer.Serialize<Dto>(_myString);
        // Dto dto = new Dto {Name = "Another Name", Age = 55} 
        // String dtoString = JsonSerializer.Deserialize<Dto>(dto);


        // Second Attempt

        // I need to be able to take in a string and turn it into an object (this is called Deserializing??)
        String randomString = "{\"Name\":\"Laptop\",\"Price\":999.99}";
        Dto myDtoObject = JsonSerializer.Deserialize<Dto>(randomString);

        // Now I want to go the other way. I want to be able to take an object that I have and turn it into a string so that I can send it over the wire
        Dto myCreatedDto = new Dto {Name="Timothy", Age=99};
        String myCreatedString = JsonSerializer.Serialize(myCreatedDto);

    }



    //Note: I looked at how to create this (what I am about to attempt to build below)
    // But now I will be attempting to build it from memory without looking to be able to get a good idea of what my current level of understanding is 
    // and so that I have more clearly cover those concepts I am missing

    public class UserLlmPrompt
    {
        public String UserName {get; set;}
        public String PromptMessage {get; set;}
    }

    public class TransformedUserLlmPrompt
    {
        public String UserName {get; set;}
        public String PromptMessage {get; set;}
        public String NewField {get; set;}
    }

    public class ResponseObject
    {
        public String LlmResponseMessage {get; set;}
    }

    // the first thing that I will need to do is to create an annotation to tell the compiler about what type the method is (I need to tell the compiler that this is a controller method and also that it is of type POST)
    // That means that if the user hits this docker container ip:port /api/(something) with a POST request, then this is the method which will get invoked.
    [HttpPost]
    public async Task<(SomeKindOfInterface)> LlmChatCall([FromBody] UserLlmPrompt requestBody)
    {
        // I will now want to take in this request body
        // I will want to parse the body of the user's request to get the useful information from it (such as the message which the user is trying to send to me)
        // But it is already an object, so that implies that whoever (I think in this case it would be Kestral) is already casting the message which the user gave to me and Deserializing it into an object of type UserLlmPrompt and passing it in as a parameter.

        // Verify body has correct parameters
        if (!requestBody.UserName || !requestBody.Age)       // I am hesitent to figure out how to get this without crashing because I want something like TryGet(requestBody.UserName)
        {
            return BadRequest();
        }
        PerformLoggingAndDataCollection(requestBody.UserName, requestBody.Age);

        // Now I think we need to send an actual http request POST to the Flask server. 
        // This means that I myself need to create an http object so that I can send it.
        // I then need to actually send it (with some kind of built in dotnet library)

        // create HTTP object
        // There is a lot that I am getting stuck on. I don't know exactly how to do this, or really what these two methods are doing
        // I was able to think of the HttpClient because I just typed Http and looked for something that seemed like it would fit
        // Then I was albe to read the message hint inside of the () for HttpClient. I didn't understand it at all, but I was able to read it and see that it was asking for someehing of type
        // HttpMessageHandler, but I have no idea what that is or what it is doing, or why I need it
        // HttpClient httpClient = new HttpClient(new HttpMessageHandler handler, ) // my first attempt
        HttpClientHandler handler = new HttpClientHandler();
        HttpClient httpClient = new HttpClient(handler);

        // Now i need to create the body
        TransformedUserLlmPrompt messageIWillSendToLangChain = new TransformedUserLlmPrompt {UserName = requestBody.UserName, PromptMessage=requestBody.PromptMessage, NewField="haha"};
        String myMessageBody = JsonSerializer(messageIWillSendToLangChain);

        // So now i want to send a post request to that flask
        var response = httpClient.Send("POST", "langchain_service:5000/api/chat", myMessageBody);

        // I don't even know what response will be but I know that i will need to go inot it and get the body and that will be the json response back from langchain flask container
        String responseFromLangchainString = response.getBody();

        //parse for the fields I am interested in
        ResponseObject res = JsonSerializer.Deserialize<ResponseObject>(responseFromLangchainString);

        if (response==StatusOk)
        {
            return GoodRequest(res.LlmResponseMessage);
        }
    }
}
*/