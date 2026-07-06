using Microsoft.AspNetCore.Mvc;
using System.Text.Json;
using System.ComponentModel.DataAnnotations;
using System.Net.Http;
using System.Text.Unicode;
using System.Text;

namespace LLM_MONITOR.server.controllers;


[ApiController] 
[Route("/api/[controller]")]
public class LlmController: ControllerBase
{
    IHttpClientFactory _httpClientFactory;
    string? _langchainContainerUrl = Environment.GetEnvironmentVariable("OLLAMA_BASE_URL");
    public LlmController(IHttpClientFactory httpClientFactory)
    {
        _httpClientFactory = httpClientFactory;
    }

    // Ultimately I am going to need to service a POST request
    // The user will send me a POST request and in the request it will have the message which they want to send to the llm
    // We need to service that request by processing their request message and parsing the contents,
    // logging the telemetry data (actually I think the logging of telemetry data should not happen here it should be in the first middleware layer)


    // I was trying to come up with the variable which I expected would be the return type. I guessed it would have been something like IHttpResponse, but it was this thing I have never heard of IActionResult. What is this?
    [HttpPost]
    public async Task<IActionResult> LlmPostEndpoint([FromBody] IncomingRequestDto incomingRequestDto )
    {
        // set up POST request to send to LangChain docker container
        // I am realizing that I don't really know how or where the userId will come from. is it the user which will generate an id for themselves? Or do I create a GUID?
        LangchainRequstDto langchainRequstDto = new LangchainRequstDto
        {
            userId = "User Not Found",
            userRequestedModel = incomingRequestDto.UserRequestedModel,
            chatMessage = incomingRequestDto.UserMessage
        };

        string? stringifiedBody = JsonSerializer.Serialize(langchainRequstDto);

        var payload = new StringContent(stringifiedBody, Encoding.UTF8,"/application/json");

        var myClient = _httpClientFactory.CreateClient();

        HttpResponseMessage langchainResponse = await myClient.PostAsync($"{_langchainContainerUrl}/api/chat", payload);

        if (!langchainResponse.IsSuccessStatusCode)
        {
            return BadRequest("LLM gave not success response");
        }

        return Ok( new {success = true, responseMessage=langchainResponse});
    }

    // The way that I title my variables needs to match up with the http request which is coming in.
    // But C# has certain standards of variable naming, and other languages have other standards.
    // So how can I develop a system (or software) that will either give a contract to the caller, or be agnostic towards the system?
    // It seems this is so fragile.
    public class IncomingRequestDto
    {
        public string? UserMessage {get; set;}
        public string? UserRequestedModel {get; set;}
    }

    public class LangchainRequstDto
    {
        public string? userId {get; set;}
        public string? chatMessage {get; set;}
        public string? userRequestedModel {get; set;}
    }
}














// [ApiController]
// [Route("/api/[controller]")]
// public class LlmController_old : ControllerBase
// {
//     private readonly IHttpClientFactory _httpClientFactory;

//     LlmController_old(IHttpClientFactory httpClientFactory)
//     {
//         _httpClientFactory = httpClientFactory;
//     }

//     // We want an endpoint which allows the user to be able to send a POST request to us 
//     // and that post request will have the message which the user wants to send to our llm
    
//     [HttpPost]
//     public async Task<IActionResult> SendChatMessage([FromBody] RequestBodyDto requestBody)
//     {
//         // I think requestBody will be auto deserialized here, so I can act upon it as a object in C#

//         // I now need to send another request to a different service
//         // I need to create my own request and send it to the api endpoint.

//         // Setup your outgoing payload for your Python service
//         var outgoingPayload = new 
//         {
//             user = requestBody.UserName,
//             prompt = requestBody.MessageToLlm
//         };

//         ResponseBodyDto responseBodyDto = new ResponseBodyDto 
//             {
//                 chatMessage = requestBody.MessageToLlm,
//                 userId = (String?)requestBody.UserName
//             };

//         // Lets serialize the object which we just created.
//         String serializedResponseBodyDto = JsonSerializer.Serialize(responseBodyDto);
//         // We also need to do encoding, but this is something which I don't really know what or why we need to do it, or what this is actually changing in my system. 
//         // Like if I am doing encoding to UTF8, is that changing the string itself, or is it adding meta data (hidden) which some other serice I don't see will look at?
        
//         // After looking at the example, I am seeing that actually it is not changing the string itself, but rather creating a new object entirely.
//         // But I don't exactly know what this object is 
//         // I also dont know what the paramaters we are passing in are doing.
//         // One more thing that I am confused about is that I am looking at the hints which 'httpClient.PostAsync' gives for the parameters and I see that it is expecting a type HttpContent, but this method says it is returning a object of StringContent. So how is this going to work? Is it that there is an overlaoder method that accepts this type of parameter? 
//         HttpContent content = new StringContent(serializedResponseBodyDto, Encoding.UTF8, "/application/json");
        
//         // Get an instance of HTTP (something) to wrap what I want to send to Langchan (my flask server in the other docker container)
//         HttpClient httpClient = _httpClientFactory.CreateClient();

//         // Now we want to actually send the message to Flask
//         try
//         {
//             // We want to hit our docker container. So we will use that container name, along with the container's port and then give the url which flask is looking for.
//             var response = await httpClient.PostAsync("langchain_service:5000/api/chat", content);

//             // At this point we should have a response back. We can now check if there was an error, and return back either an error code or the message which the llm gave to us.
//             if (!response.IsSuccessStatusCode)
//             {
//                 return BadRequest("LLM gave not success response");
//             }

//             // I guess I also now need to deserialize the response body which was given to me?
//             // LlmResponseToMeDto llmResponseToMeDto = JsonSerializer.Deserialize<LlmResponseToMeDto>(response.Body); // This was my attempt, but it obviously didn't work.

//             return Ok( new {success=true , responseMessage = response} );
//         }
//         catch
//         {
//             // This is a terrible error message. I shoudl give more information, use the logger instead.
//             Console.WriteLine("Failed in SendChatMessage Controller");
//             return BadRequest("Catch statement hit.");
//         }
        

//     }
//     public class ResponseBodyDto
//     {
//         String? userId {get; set;}
//         String? chatMessage {get; set;}
//     }

//     // After looking at my Flask contract, I see that these parameters are not valid
//     public class ResponseBodyDtoOld
//     {
//         public string LlmResposeMessage { get; set; }
//         public Guid? UserName {get; set;}
//     }
//     public class RequestBodyDto
//     {
//         [Required(ErrorMessage = "UserName is required.")]
//         public Guid? UserName { get; set; }

//         [Required(ErrorMessage = "MessageToLlm is required")]
//         [StringLength(2000, MinimumLength = 3, ErrorMessage = "Message must be between 3 and 2000 characters.")]
//         public string MessageToLlm { get; set; }
//     }

//     public class LlmResponseToMeDto
//     {
//         String? Message {get; set;}
//     }
// }
