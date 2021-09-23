from DEXcalculator import DEXcalculator

import pandas as pd
import time
import warnings


class ArbitrageAggregator:
    def __init__(self):
        self.DEX = DEXcalculator()
        self.exchangeBalances = None


    # digit_granularity : this int value determines the minimum difference between the spent amounts used to calculate prices in collectPriceData()
    # Example: If digit_granularity is 3, and the max_spent_amount is 70000, the first few spent amounts used to calculate prices are 70000, 69900, 69800...
    #          When the spent amount used 10000, the next few spent amounts used will be 9990, 9980, 9970...
    #          When the spent amount used .01, the next few spent amounts used will be .00999, .00998, .00997 ...
    def collectPriceData(self, exchange_name, spent_token, received_token, max_spent_amount, min_spent_amount, digit_granularity, save_files=True):

        #1) If all the exchanges' balances have already been stored in self.exchangeBalances, those balances are used for price calculations
        #   Otherwise, ConnectToETH.fetchBalance() is used to acquire the latest balances
        if self.exchangeBalances:
            spent_token_balance = self.exchangeBalances.get(exchange_name).get(spent_token)
            received_token_balance = self.exchangeBalances.get(exchange_name).get(received_token)
        else:
            spent_token_balance = self.DEX.fetchBalance(self.DEX.exchangeAddresses[exchange_name], self.DEX.contractAddresses[spent_token])  
            received_token_balance = self.DEX.fetchBalance(self.DEX.exchangeAddresses[exchange_name], self.DEX.contractAddresses[received_token])
        #2) Using the exchanges' balances and the chosen spending constraints, potential trade prices are calculated and stored in price_data_list
        amount_multiplier = 10**len(str(int(max_spent_amount)))
        price_data_list = []
        while amount_multiplier > min_spent_amount:
            for num in range(0, int(.9 * 10**digit_granularity)):
                spent_amount = max_spent_amount - (num / (10 ** (digit_granularity - 1))) * (amount_multiplier / 10)
                price = self.DEX.calculatePrice(spent_token_balance, received_token_balance, spent_amount)
                inverse_price = 1 / price
                received_amount = round(spent_amount / price, 18)
                new_data_entry = {'Exchange': exchange_name, \
                                  'Spent Token': spent_token, \
                                  'Price ('+spent_token+')': price, \
                                  'Price ('+received_token+')': inverse_price, \
                                  'Spent Amount': spent_amount, \
                                  'Received Amount': received_amount}
                price_data_list.append(new_data_entry)
                if spent_amount <= amount_multiplier / 10:
                    break
                if not(price):
                    amount_multiplier = 0
                    break
            max_spent_amount = amount_multiplier / 10
            amount_multiplier = amount_multiplier / 10
            
        #3) price_data_list is converted to a DataFrame and exported to CSV to facilitate automated and manual analysis
        price_dataframe = pd.DataFrame(price_data_list, columns=list(new_data_entry))
        if save_files:
            self.saveDataToCSV(price_dataframe, exchange_name + ' ' + spent_token + '-' + received_token)
        return(price_dataframe)


    def collectPriceDataOnAllExchanges(self, spent_token, received_token, max_spent_amount, min_spent_amount, digit_granularity, silent_mode=False):
        price_dataframe_dict = {}
        if not(self.exchangeBalances):
            self.exchangeBalances = self.DEX.fetchExchangeBalances(silent_mode)
        for exchange_name in self.exchangeBalances:
            price_dataframe = self.collectPriceData(exchange_name, spent_token, received_token, max_spent_amount, min_spent_amount, digit_granularity, save_files=not(silent_mode))
            price_dataframe_dict[exchange_name] = price_dataframe
        return(price_dataframe_dict)


    def checkForArbitrage(self, token_A, token_B, max_spent_amount, min_spent_amount, digit_granularity, silent_mode=False):
        #1) Prices for spending token_A across exchanges are calculated and stored in token_A_data
        self.exchangeBalances = self.DEX.fetchExchangeBalances(silent_mode=True)
        token_A_data = self.collectPriceDataOnAllExchanges(token_A, token_B, max_spent_amount, min_spent_amount, digit_granularity, silent_mode)

        #2) token_A_data is checked for arbitrage opportunities by comparing prices across exchanges
        arbitrage_data_list = []
        start_time = int(time.time())
        for exchange_name_A in token_A_data:
            for exchange_name_B in token_A_data:
                if exchange_name_A != exchange_name_B:
                    if not(silent_mode):
                        print('\nCalculating arbitrage opportunities for buying ' + token_B + ' on ' + exchange_name_A + ' and selling it on ' + exchange_name_B + '...')
                    number_of_arbitrage_opportunities_found = len(arbitrage_data_list)
                    for index_A in token_A_data[exchange_name_A].index:
                        # The row at index_A contains an amount of token_A that can be spent for an amount of token_B on exchange_A 
                        # Using that amount of token_B that could be bought on exchange_A, a new price is calculated for a second trade on exchange_B
                        # Using that price, the amount of token_A that can be bought using token_B on exchange_B is calculated
                        # The pair of trades is an arbitrage opportunity if the amount of token_A bought in the second trade is greater than the amount spent in the first
                        token_B_amount_bought = token_A_data[exchange_name_A]['Received Amount'][index_A]
                        token_B_sell_price = self.DEX.calculatePrice(self.exchangeBalances[exchange_name_B][token_B], \
                                                                     self.exchangeBalances[exchange_name_B][token_A], token_B_amount_bought)
                        token_A_amount_received = round(token_B_amount_bought / token_B_sell_price, 18)
                        total_profit = token_A_amount_received - token_A_data[exchange_name_A]['Spent Amount'][index_A]
                        if total_profit > 0:
                            new_data_entry = {'Buy Exchange': exchange_name_A, \
                                              'Sell Exchange': exchange_name_B, \
                                              'Buy Price ('+token_A+')': token_A_data[exchange_name_A]['Price ('+token_A+')'][index_A], \
                                              'Sell Price ('+token_A+')': 1 / token_B_sell_price, \
                                              'Traded Amount ('+token_B+')': token_B_amount_bought, \
                                              'Spent Amount ('+token_A+')': token_A_data[exchange_name_A]['Spent Amount'][index_A], \
                                              'Received Amount ('+token_A+')': token_A_amount_received, \
                                              'Trade Profit ('+token_A+')': total_profit}
                            arbitrage_data_list.append(new_data_entry)
                    if not(silent_mode):
                        print('    ' + str(len(arbitrage_data_list) - number_of_arbitrage_opportunities_found) + ' arbitrage opportunities found!')
                        run_time = int(time.time()) - start_time
                        print('\nRun Time: ' + str(int(run_time / 60)) + ' minutes ' + str(run_time % 60) + ' seconds')

        #3) arbitrage_data_list is converted to a DataFrame and exported to CSV to facilitate automated and manual analysis
        arbitrage_dataframe = pd.DataFrame(arbitrage_data_list, columns=list(new_data_entry))
        if not(silent_mode):
            file_name = self.saveDataToCSV(arbitrage_dataframe, 'ArbitrageOpportunities')
            print('\nArbitrage data saved to ' + file_name)
        print('\nA total of ' + str(sum(arbitrage_dataframe['Trade Profit ('+token_A+')'])) + ' ' + token_A + \
              ' in arbitrage profits was found across ' + str(len(arbitrage_dataframe)) + ' trades.')
        return(arbitrage_dataframe)


    def loopArbitrageDetection(self, token_A, token_B, max_spent_amount, min_spent_amount, digit_granularity):
        collect_data = True
        arbitrage_statistics_list = []
        start_time = int(time.time())
        # Irrelevant warnings sometimes occur while looping with older versions of pandas, so they are ignored
        warnings.filterwarnings("ignore")
        
        #1) This while loop will repetitively use checkForArbitrage() to collect data on potential arbitrage opportunities across exchanges
        #   The loop will run indefinitely until keyboard interrupt or an error
        while collect_data:
            try:
                arbitrage_dataframe = self.checkForArbitrage(token_A, token_B, max_spent_amount, min_spent_amount, digit_granularity, silent_mode=True)
                new_statistics_entry = {}
                for buy_exchange in self.exchangeBalances:
                    for sell_exchange in self.exchangeBalances:
                        if buy_exchange != sell_exchange:
                            
                            #2) A truncated DataFrame containing only arbitrage opportunities between a particular pair of exchanges is created
                            #   This truncated DataFrame is used to generate statistical data for comparison with other pairs of exchanges
                            exchange_pair = buy_exchange + '-' + sell_exchange
                            exchange_pair_dataframe = arbitrage_dataframe[arbitrage_dataframe['Buy Exchange'] == buy_exchange]\
                                                      [arbitrage_dataframe['Sell Exchange'] == sell_exchange]
                            new_statistics_entry.update({exchange_pair + ' # of Profitable Trades': len(exchange_pair_dataframe), \
                                                         exchange_pair + ' Total Profit': sum(exchange_pair_dataframe['Trade Profit ('+token_A+')']), \
                                                         exchange_pair + ' Biggest Trade Profit': exchange_pair_dataframe['Trade Profit ('+token_A+')'].max(), \
                                                         exchange_pair + ' Average Profit': exchange_pair_dataframe['Trade Profit ('+token_A+')'].mean(), \
                                                         exchange_pair + ' Median Profit': exchange_pair_dataframe['Trade Profit ('+token_A+')'].median()})

                #3) Statistics about the different arbitrage opportunities, along with the current run time and block number, are stored in arbitrage_statistics_list
                latest_block_number = self.DEX.fetchLatestBlockNumber()
                run_time = int(time.time()) - start_time
                print('Run Time: ' + str(int(run_time / 60)) + ' minutes ' + str(run_time % 60) + ' seconds')
                new_statistics_entry['Run Time (seconds)'] = run_time
                new_statistics_entry['Block Number'] = latest_block_number
                arbitrage_statistics_list.append(new_statistics_entry)
                print('Loop Count: ' + str(len(arbitrage_statistics_list)))
            except KeyboardInterrupt as error:
                print('\nEnding Arbitrage Detection Loop...')
                collect_data = False
            except Exception as error:
                print('\nERROR! Arbitrage Detection Loop ended due to unexpected error: ' + str(error))
                collect_data = False

        #4) In the case of keyboard interruption or an unintentional error, arbitrage_statistics_dataframe is converted to a DataFrame and exported to CSV
        arbitrage_statistics_dataframe = pd.DataFrame(arbitrage_statistics_list, columns=list(new_statistics_entry))
        file_name = self.saveDataToCSV(arbitrage_statistics_dataframe, 'ArbitrageDetectionStats')
        print('\nArbitrage statistics saved to ' + file_name)
        warnings.filterwarnings("default")
        return(arbitrage_statistics_dataframe)
            

    # Saves DataFrame objects to CSV with the current date and time in the file name
    def saveDataToCSV(self, data, file_name):
        date_time = list(time.localtime())
        full_file_name = file_name + '_' + str(date_time[1]) + '-' + str(date_time[2]) + '-' + str(date_time[0]) + '_' + \
                         '0'*(2 - len(str(date_time[3]))) + str(date_time[3]) + '-' + '0'*(2-len(str(date_time[4])))+ \
                         str(date_time[4]) + '-' + '0'*(2-len(str(date_time[5]))) + str(date_time[5]) + '.csv'
        data.to_csv(full_file_name)
        return(full_file_name)
