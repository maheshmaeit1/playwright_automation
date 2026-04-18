// Generated from: features\search.feature
import { test } from "playwright-bdd";

test.describe('Product search', () => {

  test('Exact product name search returns only Wireless Headphones', async ({ Given, When, Then, And, page }) => { 
    await Given('the user opens the EcoShop home page', null, { page }); 
    await When('the user searches for "Wireless Headphones"', null, { page }); 
    await Then('the product count shows 1 result', null, { page }); 
    await And('the product heading "Wireless Headphones" is visible', null, { page }); 
    await And('only 1 Add to Cart button is visible', null, { page }); 
  });

});

// == technical section ==

test.use({
  $test: [({}, use) => use(test), { scope: 'test', box: true }],
  $uri: [({}, use) => use('features\\search.feature'), { scope: 'test', box: true }],
  $bddFileData: [({}, use) => use(bddFileData), { scope: "test", box: true }],
});

const bddFileData = [ // bdd-data-start
  {"pwTestLine":6,"pickleLine":6,"tags":[],"steps":[{"pwStepLine":7,"gherkinStepLine":7,"keywordType":"Context","textWithKeyword":"Given the user opens the EcoShop home page","stepMatchArguments":[]},{"pwStepLine":8,"gherkinStepLine":8,"keywordType":"Action","textWithKeyword":"When the user searches for \"Wireless Headphones\"","stepMatchArguments":[{"group":{"start":22,"value":"\"Wireless Headphones\"","children":[{"start":23,"value":"Wireless Headphones","children":[{"children":[]}]},{"children":[{"children":[]}]}]},"parameterTypeName":"string"}]},{"pwStepLine":9,"gherkinStepLine":9,"keywordType":"Outcome","textWithKeyword":"Then the product count shows 1 result","stepMatchArguments":[]},{"pwStepLine":10,"gherkinStepLine":10,"keywordType":"Outcome","textWithKeyword":"And the product heading \"Wireless Headphones\" is visible","stepMatchArguments":[{"group":{"start":20,"value":"\"Wireless Headphones\"","children":[{"start":21,"value":"Wireless Headphones","children":[{"children":[]}]},{"children":[{"children":[]}]}]},"parameterTypeName":"string"}]},{"pwStepLine":11,"gherkinStepLine":11,"keywordType":"Outcome","textWithKeyword":"And only 1 Add to Cart button is visible","stepMatchArguments":[]}]},
]; // bdd-data-end